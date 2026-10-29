#!/usr/bin/env python3
"""Synchronize supported OJs and merge manually curated records.

Optional authorized session cookies come only from the private server environment.
No remote judging or source-code downloads.
Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime as dt
from html.parser import HTMLParser
from html import unescape
from http.cookiejar import CookieJar, Cookie
import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name == 'tools':
    ROOT = ROOT.parent
CONFIG = ROOT / 'config' / 'oj_sources.json'
ASSETS = ROOT / 'source' / 'algo' if (ROOT / 'source' / 'algo').is_dir() else ROOT / 'algo'
OUTPUT = ASSETS / 'data.json'
MANUAL = ROOT / 'data' / 'manual.csv'
MANUAL_CONTESTS = ROOT / 'data' / 'contests.csv'
AGENT = 'lostin-oj-hub/2.0 (+github.com/00lostin00/00lostin00.github.io)'
HTTP_SESSION = threading.local()
HTTP_BUDGET_LOCK = threading.Lock()
HTTP_HOST_LOCKS = {}
HTTP_LAST_REQUEST = {}


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def iso_from_unix(value):
    try:
        return dt.datetime.fromtimestamp(int(value), dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    except (ValueError, OverflowError, TypeError):
        return None


def to_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_json(path, default):
    try:
        with Path(path).open(encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def get_text(url, attempts=3, headers=None):
    err = None
    if not hasattr(HTTP_SESSION,'opener'):
        HTTP_SESSION.cookies=CookieJar()
        HTTP_SESSION.cookie_seeds={}
        HTTP_SESSION.opener=build_opener(HTTPCookieProcessor(HTTP_SESSION.cookies))
    headers=dict(headers or {})
    seed=headers.pop('Cookie',None)
    if seed:
        host=urlsplit(url).hostname
        signature=hashlib.sha256(seed.encode()).digest()
        if HTTP_SESSION.cookie_seeds.get(host)!=signature:
            for item in seed.split(';'):
                if '=' not in item:continue
                name,value=item.strip().split('=',1)
                HTTP_SESSION.cookies.set_cookie(Cookie(0,name,value,None,False,host,False,False,'/',True,
                    urlsplit(url).scheme=='https',None,True,None,None,{}))
            HTTP_SESSION.cookie_seeds[host]=signature
    # Let the cookie jar apply Set-Cookie during redirects. An explicit Cookie
    # request header would freeze the old C3VK value and cause a redirect loop.
    for trial in range(attempts):
        try:
            host=urlsplit(url).hostname
            gap={'codeforces.com':2.1,'kenkoooo.com':1.2,'www.luogu.com.cn':1.2,'ac.nowcoder.com':1.1,'www.algowiki.cn':1.0,'www.acwing.com':1.5}.get(host,0)
            if host=='www.luogu.com.cn' and urlsplit(url).path.startswith('/problem/') and not urlsplit(url).path.endswith('/list'):gap=4
            if gap:
                with HTTP_BUDGET_LOCK:host_lock=HTTP_HOST_LOCKS.setdefault(host,threading.Lock())
                with host_lock:
                    delay=gap-(time.monotonic()-HTTP_LAST_REQUEST.get(host,0))
                    if delay>0:time.sleep(delay)
                    HTTP_LAST_REQUEST[host]=time.monotonic()
            request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; lostin-archive/3.0)', 'Accept': 'application/json,text/html', **headers})
            with HTTP_SESSION.opener.open(request, timeout=25) as response:
                body=response.read()
                if response.headers.get('Content-Encoding','').lower()=='gzip':body=gzip.decompress(body)
                encoding=response.headers.get_content_charset() or 'utf-8'
                return body.decode('gb18030' if encoding.lower() in ['gb2312','gbk'] else encoding)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            err = exc
            if isinstance(exc, HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            if trial + 1 < attempts:
                time.sleep(2 + trial * 3)
    # Do not include headers/cookies or login redirect URLs in public errors.
    status=f'HTTP {err.code}' if isinstance(err,HTTPError) else type(err).__name__
    raise RuntimeError(f'{url.split("?")[0]} unavailable ({status})')


def get_json(url, attempts=3, headers=None):
    return json.loads(get_text(url, attempts=attempts, headers=headers))


def session_headers(platform):
    cookie=re.sub(r'^cookie:\s*','',os.environ.get(platform.upper()+'_COOKIE','').strip(),flags=re.I)
    if cookie and not re.search(r'(?:^|;\s*)[^=;\s]+\s*=',cookie):
        raise ValueError('私有登录态格式无效；需要完整的 name=value Cookie 请求头')
    headers={'User-Agent':os.environ.get(platform.upper()+'_USER_AGENT') or 'Mozilla/5.0'}
    if cookie:headers['Cookie']=cookie
    return headers


def cf_api(method, **params):
    params.setdefault('lang', 'en')
    result = get_json('https://codeforces.com/api/' + method + '?' + urlencode(params))
    if not isinstance(result, dict) or result.get('status') != 'OK':
        raise RuntimeError('Codeforces API: ' + str(result.get('comment', 'unexpected response')))
    return result.get('result')


def cf_problem(submission):
    if submission.get('verdict') != 'OK':
        return None
    p = submission.get('problem') or {}
    cid = p.get('contestId')
    idx = p.get('index')
    if cid is None or not idx:
        return None
    problem_id = str(cid) + str(idx)
    route = 'gym' if int(cid) >= 100000 else 'contest'
    return {
        'platform': 'codeforces', 'id': problem_id,
        'title': p.get('name', problem_id),
        'url': f'https://codeforces.com/{route}/{cid}/problem/{quote(str(idx))}',
        'status': 'AC', 'rating': to_int(p.get('rating')), 'level': '',
        'tags': p.get('tags') if isinstance(p.get('tags'), list) else [],
        'accepted_at': iso_from_unix(submission.get('creationTimeSeconds')),
        'first_accepted_at': iso_from_unix(submission.get('creationTimeSeconds')),
        'source': 'api', 'notes': ''
    }


def merge_problems(existing, incoming):
    """Keep latest submission metadata AND the earliest verified AC timestamp."""
    by_id = {}
    for p in existing + incoming:
        if not isinstance(p, dict):
            continue
        platform = str(p.get('platform', '')).strip().lower()
        pid = str(p.get('id', '')).strip()
        if not platform or not pid:
            continue
        key = (platform, pid.lower())
        current = by_id.get(key)
        earliest = min((v for v in ((current or {}).get('first_accepted_at'), p.get('first_accepted_at')) if v), default=None)
        if current is None:
            by_id[key] = p
        elif p.get('status') == 'AC' and current.get('status') != 'AC':
            by_id[key] = p
        elif (p.get('status') == 'AC') == (current.get('status') == 'AC'):
            if (p.get('accepted_at') or '') >= (current.get('accepted_at') or ''):
                by_id[key] = p
        if earliest:
            by_id[key] = {**by_id[key], 'first_accepted_at': earliest}
    return list(by_id.values())


def pull_codeforces(handle, previous, sleep=time.sleep):
    previous_problems = [p for p in previous.get('problems', []) if p.get('platform') == 'codeforces' and p.get('source') == 'api']
    submissions = []
    page_size = 1000
    max_pages = max(1, int(os.environ.get('CF_MAX_PAGES', '40')))
    complete = False
    prior = next((p for p in previous.get('platforms', []) if p.get('id') == 'codeforces'), {})
    incremental = bool(prior.get('history_complete')) and all(p.get('first_accepted_at') for p in previous_problems)
    watermark = int(prior.get('cursor') or 0) if incremental else 0
    for page in range(max_pages):
        if page:
            sleep(2.1)  # Respect Codeforces public API call limits.
        batch = cf_api('user.status', handle=handle, **{'from': page * page_size + 1, 'count': page_size})
        if not isinstance(batch, list):
            raise RuntimeError('Codeforces user.status returned an unexpected payload')
        submissions.extend(batch)
        if len(batch) < page_size:
            complete = True
            break
        if watermark and any(int(s.get('id') or 0) <= watermark for s in batch):
            complete = True
            break
    problems = merge_problems(previous_problems if incremental or not complete else [],
                              [p for s in submissions if (p := cf_problem(s))])
    sleep(2.1)
    history_raw = cf_api('user.rating', handle=handle)
    sleep(2.1)
    users = cf_api('user.info', handles=handle)
    user = users[0] if users else {}
    ratings = [{
        'time': iso_from_unix(r.get('ratingUpdateTimeSeconds')),
        'rating': to_int(r.get('newRating'))
    } for r in history_raw]
    contests = [{
        'platform': 'codeforces', 'id': str(r.get('contestId')),
        'title': r.get('contestName', 'Codeforces Round'),
        'url': f'https://codeforces.com/contest/{r.get("contestId")}',
        'date': iso_from_unix(r.get('ratingUpdateTimeSeconds')),
        'rank': to_int(r.get('rank')),
        'old_rating': to_int(r.get('oldRating')),
        'new_rating': to_int(r.get('newRating')),
        'delta': (r.get('newRating', 0) - r.get('oldRating', 0)),
        'source': 'api'
    } for r in history_raw]
    return {'problems': problems, 'contests': contests,
            'rating': {'current': to_int(user.get('rating')),
                       'max': to_int(user.get('maxRating')),
                       'rank': user.get('rank', ''),
                       'history': ratings},
            'partial': not complete, 'history_complete': complete,
            'cursor': max((int(s.get('id') or 0) for s in submissions), default=watermark)}


def ac_problem(submission, titles):
    if submission.get('result') != 'AC':
        return None
    pid = str(submission.get('problem_id', '')).strip()
    cid = str(submission.get('contest_id', '')).strip()
    if not pid or not cid:
        return None
    suffix = pid.rsplit('_', 1)[-1]
    return {
        'platform': 'atcoder', 'id': pid,
        'title': titles.get(pid, pid),
        'url': f'https://atcoder.jp/contests/{quote(cid)}/tasks/{quote(pid)}',
        'status': 'AC', 'rating': None,
        'level': suffix.upper() if len(suffix) == 1 and suffix.isalpha() else '',
        'tags': [], 'accepted_at': iso_from_unix(submission.get('epoch_second')),
        'first_accepted_at': iso_from_unix(submission.get('epoch_second')),
        'source': 'api', 'notes': ''
    }


def pull_atcoder(handle, previous, sleep=time.sleep):
    old_platform = next((p for p in previous.get('platforms', []) if p.get('id') == 'atcoder'), {})
    cursor = max(0, int(old_platform.get('cursor') or 0))
    if not old_platform.get('history_complete'):
        cursor = 0
    second = max(0, cursor - 1)
    page_limit = max(1, int(os.environ.get('ATCODER_MAX_PAGES', '40')))
    accepted = []
    newest = cursor
    complete = False
    for page in range(page_limit):
        if page:
            sleep(1.2)
        batch = get_json('https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?' +
                         urlencode({'user': handle, 'from_second': second}))
        if not isinstance(batch, list):
            raise RuntimeError('AtCoder Problems submissions endpoint returned a non-list')
        accepted.extend(s for s in batch if s.get('result') == 'AC')
        if batch:
            newest = max(newest, max(int(s.get('epoch_second') or 0) for s in batch))
        if len(batch) < 500:
            complete = True
            break
        next_second = max(int(s.get('epoch_second') or 0) for s in batch) + 1
        if next_second <= second:
            raise RuntimeError('AtCoder submissions cursor did not advance')
        second = next_second
    titles = {}
    if accepted:
        try:
            sleep(1.2)
            resources = get_json('https://kenkoooo.com/atcoder/resources/problems.json')
            titles = {str(p.get('id')): str(p.get('title') or p.get('id')) for p in resources if isinstance(p, dict)}
        except Exception as exc:
            print(f'warning: AtCoder problem titles unavailable: {exc}', file=sys.stderr)
    previous_problems = [p for p in previous.get('problems', []) if p.get('platform') == 'atcoder' and p.get('source') == 'api']
    problems = merge_problems(previous_problems, [p for s in accepted if (p := ac_problem(s, titles))])
    if any(p.get('rating') is None for p in problems):
        try:
            sleep(1.2)
            models=get_json('https://kenkoooo.com/atcoder/resources/problem-models.json')
            for p in problems:
                estimate=(models.get(p['id']) or {}).get('difficulty')
                if estimate is not None:
                    p['rating']=to_int(estimate)
                    p['difficulty_source']='atcoder-problems-estimate'
        except Exception:
            print('warning: AtCoder estimated difficulty unavailable; keep unknown values',file=sys.stderr)
    contests = []
    rating = previous.get('ratings', {}).get('atcoder', {})
    try:
        sleep(1.2)
        history = get_json('https://atcoder.jp/users/' + quote(handle) + '/history/json', attempts=2)
        if not isinstance(history, list):
            raise RuntimeError('non-list rating history')
        rated = [h for h in history if h.get('IsRated')]
        points = [{'time': h.get('EndTime'), 'rating': to_int(h.get('NewRating'))} for h in rated]
        rating = {'current': points[-1]['rating'] if points else None,
                  'max': max((p['rating'] for p in points if p['rating'] is not None), default=None),
                  'rank': '', 'history': points}
        contests = [{
            'platform': 'atcoder', 'id': str(h.get('ContestScreenName', h.get('ContestName', ''))),
            'title': h.get('ContestName', 'AtCoder Contest'),
            'url': 'https://atcoder.jp/users/' + quote(handle) + '/history',
            'date': h.get('EndTime'), 'rank': to_int(h.get('Place')),
            'old_rating': to_int(h.get('OldRating')), 'new_rating': to_int(h.get('NewRating')),
            'delta': (h.get('NewRating', 0) - h.get('OldRating', 0)),
            'source': 'api'
        } for h in rated]
    except Exception as exc:
        # A history outage must not discard accepted problems.
        print(f'warning: AtCoder rating history unavailable: {exc}', file=sys.stderr)
        contests = [c for c in previous.get('contests', []) if c.get('platform') == 'atcoder' and c.get('source') == 'api']
    return {'problems': problems, 'contests': contests,
            'rating': rating, 'partial': not complete, 'history_complete': complete,
            'cursor': newest if complete else cursor}


class SubmissionTable(HTMLParser):
    """Read visible table cells and links; no source-code pages are fetched."""
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None; self.depth=0

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='tr': self.row=[]
        if tag=='td' and self.row is not None: self.cell={'text':'','links':[]}
        if tag=='a' and self.cell is not None: self.cell['links'].append(attrs.get('href',''))

    def handle_data(self, data):
        if self.cell is not None: self.cell['text']+=data

    def handle_endtag(self, tag):
        if tag=='td' and self.cell is not None:
            self.cell['text']=' '.join(self.cell['text'].split()); self.row.append(self.cell);self.cell=None
        if tag=='tr' and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None


def html_problems(text, platform):
    parser=SubmissionTable();parser.feed(text); records=[]
    for cells in parser.rows:
        body=' '.join(c['text'] for c in cells)
        if not re.search(r'答案正确|Accepted|\bAC\b',body,re.I):continue
        problem=next(((c,link) for c in cells for link in c['links'] if re.search(r'/problem/[^/?]+',link)),None)
        if not problem:continue
        cell,link=problem;pid=re.search(r'/problem/([^/?]+)',link).group(1)
        if not any(c is not cell and re.fullmatch(r'(?:答案正确|Accepted|AC)(?:\s*\([^)]*\))?',c['text'],re.I) for c in cells):continue
        date=re.search(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?',body)
        timestamp=None
        if date:
            timestamp=dt.datetime.fromisoformat(date.group().replace('T',' ')).replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
        records.append({'platform':platform,'id':pid,'title':cell['text'] or pid,
            'url':urljoin('https://ac.nowcoder.com' if platform=='nowcoder' else 'https://qoj.ac',link),
            'status':'AC','rating':None,'level':'','tags':[],'accepted_at':timestamp,
            'first_accepted_at':timestamp,'source':'api','notes':''})
    return records, len(parser.rows)


def pull_html_platform(platform, handle, previous, sleep=time.sleep):
    if platform=='nowcoder' and not str(handle).isdigit():raise ValueError('牛客需要数字用户 ID')
    old=[p for p in previous.get('problems',[]) if p.get('platform')==platform and p.get('source')=='api']
    records=[];complete=False;fingerprints=set()
    headers=session_headers(platform)
    for page in range(1,max(1,int(os.environ.get('HTML_MAX_PAGES','80')))+1):
        if page>1:sleep(1.2)
        if platform=='nowcoder':
            url=f'https://ac.nowcoder.com/acm/contest/profile/{quote(str(handle))}/practice-coding?'+urlencode({'page':page,'pageSize':100,'statusTypeFilter':5,'orderType':'DESC'})
        else:url='https://qoj.ac/submissions?'+urlencode({'submitter':handle,'page':page})
        text=get_text(url,attempts=1,headers=headers)
        if re.search(r'验证码|Access denied|Just a moment|登录后查看',text,re.I):raise RuntimeError('上游要求登录或验证；保留已有缓存')
        batch,row_count=html_problems(text,platform)
        fingerprint=tuple((p['id'],p['accepted_at']) for p in batch)
        if batch and fingerprint in fingerprints:raise RuntimeError('上游分页未前进；保留已有缓存')
        fingerprints.add(fingerprint);records.extend(batch)
        if not row_count:
            if page==1 and not re.search(r'暂无|没有.*记录|No submissions|No records',text,re.I):raise RuntimeError('上游页面格式不匹配，无法确认题目记录')
            complete=True;break
        if platform=='nowcoder':
            next_page=re.search(r'<li[^>]*class="[^"]*js-next-pager[^"]*"[^>]*>(.*?)</li>',text,re.S)
            if not next_page or 'disabled' in next_page.group(0).split('>')[0]:complete=True;break
        elif not re.search(r'(?:page='+str(page+1)+r'\b|下一页|Next)',text,re.I):complete=True;break
    return {'problems':merge_problems([] if complete else old,records),'contests':[c for c in previous.get('contests',[]) if c.get('platform')==platform and c.get('source')=='api'],
        'rating':previous.get('ratings',{}).get(platform,{}),'partial':not complete,'history_complete':complete,'cursor':None}


def pull_nowcoder(handle, previous):return pull_html_platform('nowcoder',handle,previous)
def pull_qoj(handle, previous):return pull_html_platform('qoj',handle,previous)


def pull_acwing(handle,previous):
    from sync_acwing import pull
    return pull(handle,previous)


def pull_luogu(handle, previous, sleep=time.sleep):
    if not str(handle).isdigit():raise ValueError('洛谷需要数字用户 ID')
    records=[];complete=False;seen_rows=0
    old=[p for p in previous.get('problems',[]) if p.get('platform')=='luogu' and p.get('source')=='api']
    old_platform=next((p for p in previous.get('platforms',[]) if p.get('id')=='luogu'),{})
    incremental=bool(old_platform.get('history_complete')) and all(p.get('first_accepted_at') for p in old)
    watermark=int(old_platform.get('cursor') or 0) if incremental else 0
    newest=watermark
    headers={**session_headers('luogu'),'x-lentille-request':'content-only'}
    for page in range(1,max(1,int(os.environ.get('LUOGU_MAX_PAGES','300')))+1):
        if page>1:sleep(1.2)
        data=get_json('https://www.luogu.com.cn/record/list?'+urlencode({'user':handle,'status':12,'page':page}),attempts=1,headers=headers)
        payload=data.get('data') or data.get('currentData') or data
        listing=payload.get('records',{});batch=listing.get('result') if isinstance(listing,dict) else listing
        if not isinstance(batch,list):raise RuntimeError('洛谷接口未返回公开提交记录；可能需要配置 LUOGU_COOKIE')
        seen_rows+=len(batch)
        newest=max(newest,max((int(row.get('id') or 0) for row in batch),default=0))
        for row in batch:
            p=row.get('problem') or {};pid=p.get('pid');user=(row.get('user') or {}).get('uid')
            if not pid or row.get('status')!=12 or (user is not None and str(user)!=str(handle)):continue
            timestamp=iso_from_unix(row.get('submitTime'))
            records.append({'platform':'luogu','id':pid,'title':p.get('name') or p.get('title') or pid,'url':'https://www.luogu.com.cn/problem/'+quote(pid),
                'status':'AC','rating':None,'level':{0:'未评定',1:'入门',2:'普及−',3:'普及/提高−',4:'普及+/提高',5:'提高+/省选−',6:'省选/NOI−',7:'NOI/NOI+/CTSC'}.get(p.get('difficulty'),''),
                'tags':[str(x) for x in p.get('tags',[]) if isinstance(x,str)],'accepted_at':timestamp,'first_accepted_at':timestamp,'source':'api','notes':''})
        total=listing.get('count') if isinstance(listing,dict) else None
        if not batch or total is not None and seen_rows>=int(total):complete=True;break
        if watermark and any(int(row.get('id') or 0)<=watermark for row in batch):complete=True;break
    return {'problems':merge_problems(old if incremental or not complete else [],records),'contests':[],'rating':{},'partial':not complete,'history_complete':complete,'cursor':newest}


def csv_rows(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def manual_problems(path):
    records = []
    for number, row in enumerate(csv_rows(path), 2):
        platform = (row.get('platform') or '').lower().strip()
        pid = (row.get('id') or '').strip()
        if not platform or not pid:
            print(f'warning: manual.csv line {number} omitted: platform or id empty', file=sys.stderr)
            continue
        raw_status = (row.get('status') or 'TODO').strip().upper()
        status = raw_status if raw_status in ('AC', 'TODO', 'REVIEW', 'WA') else 'TODO'
        records.append({
            'platform': platform, 'id': pid,
            'title': (row.get('title') or pid).strip(),
            'url': (row.get('url') or '').strip(),
            'status': status, 'rating': to_int(row.get('rating')),
            'level': (row.get('level') or '').strip(),
            'tags': [t.strip() for t in (row.get('tags') or '').split(';') if t.strip()],
            'accepted_at': (row.get('accepted_at') or '').strip() or None,
            'first_accepted_at': (row.get('first_accepted_at') or row.get('accepted_at') or '').strip() or None,
            'source': 'manual', 'notes': (row.get('notes') or '').strip()
        })
    return records


def manual_contests(path):
    results = []
    for row in csv_rows(path):
        if not (row.get('platform') and row.get('title')):
            continue
        results.append({
            'platform': row['platform'].lower().strip(), 'id': str(row.get('id') or row['title']).strip(),
            'title': row['title'].strip(), 'url': (row.get('url') or '').strip(),
            'date': (row.get('date') or '').strip(),
            'rank': to_int(row.get('rank')), 'solved': to_int(row.get('solved')),
            'penalty': to_int(row.get('penalty')),
            'notes': (row.get('notes') or '').strip(), 'source': 'manual'
        })
    return results


def combine_auto_manual(automatic, manual):
    """Preserve official AC, overlay manual notes/tags; manual AC is allowed as self-reported."""
    by_key = {(p['platform'], p['id'].lower()): dict(p) for p in automatic}
    for p in manual:
        key = (p['platform'], p['id'].lower())
        old = by_key.get(key)
        if old:
            combined = dict(old)
            if p.get('notes'):
                combined['notes'] = p['notes']
            if p.get('tags'):
                combined['tags'] = sorted(set((old.get('tags') or []) + p['tags']))
            if old.get('rating') is None and p.get('rating') is not None:
                combined['rating'] = p['rating']
            # Do not downgrade a verified AC using a manually entered TODO.
            if old.get('status') != 'AC' and p.get('status') == 'AC':
                combined.update(p)
            by_key[key] = combined
        else:
            by_key[key] = p
    return sorted(by_key.values(), key=lambda p: (p.get('accepted_at') or '', p['platform'], p['id']), reverse=True)


def assemble(config, previous, local_problems, local_contests, offline=False, pulls=None):
    pulls = pulls or {'codeforces': pull_codeforces, 'atcoder': pull_atcoder, 'nowcoder':pull_nowcoder, 'luogu':pull_luogu, 'qoj':pull_qoj,'acwing':pull_acwing}
    futures = {}
    executor = ThreadPoolExecutor(max_workers=5) if not offline else None
    if executor:
        for entry in config.get('platforms', []):
            if entry.get('mode') == 'auto' and entry.get('handle') and entry.get('id') in pulls:
                futures[entry['id']] = executor.submit(pulls[entry['id']], str(entry['handle']).strip(), previous)
    platforms = []
    auto_problems = [p for p in previous.get('problems', []) if p.get('source') == 'api']
    auto_contests = [c for c in previous.get('contests', []) if c.get('source') == 'api']
    ratings = dict(previous.get('ratings') or {})
    old_info = {p.get('id'): p for p in previous.get('platforms', [])}
    for platform in config.get('platforms', []):
        p = dict(platform)
        slug = p.get('id')
        handle = str(p.get('handle') or '').strip()
        old = old_info.get(slug, {})
        p['cursor'] = old.get('cursor')
        p['last_ok'] = old.get('last_ok')
        p['history_complete'] = old.get('history_complete',False)
        p['error'] = ''
        if p.get('mode') != 'auto':
            p['sync_status'] = 'manual'
        elif not handle:
            p['sync_status'] = 'not_configured'
        elif offline:
            p['sync_status'] = 'offline'
        else:
            try:
                result = futures[slug].result()
                auto_problems = [a for a in auto_problems if a.get('platform') != slug] + result['problems']
                auto_contests = [c for c in auto_contests if c.get('platform') != slug] + result['contests']
                ratings[slug] = result['rating']
                p['cursor'] = result.get('cursor')
                p['history_complete'] = result.get('history_complete',not result.get('partial'))
                p['last_ok'] = now_iso()
                p['sync_status'] = 'partial' if result.get('partial') else 'ok'
            except Exception as exc:
                p['sync_status'] = 'blocked' if re.search(r'HTTP (401|403)',str(exc)) else 'error'
                p['error'] = str(exc)[:200]
                print(f'warning: {slug} synchronization failed: {exc}', file=sys.stderr)
        platforms.append(p)
    if executor:
        executor.shutdown(wait=True)
    existing = {p['id'] for p in platforms}
    for item in local_problems + [c for c in local_contests]:
        slug = item['platform']
        if slug not in existing:
            # Extensible without modifying JavaScript; accepts arbitrary custom OJ IDs.
            platforms.append({'id': slug, 'name': slug, 'short': slug[:4].upper(),
                              'home': '', 'profile_template': '', 'handle': '',
                              'mode': 'manual', 'accent': '#92afcc', 'group': '自定义',
                              'sync_status': 'manual', 'last_ok': None, 'error': ''})
            existing.add(slug)
    problems = combine_auto_manual(auto_problems, local_problems)
    contests = auto_contests + local_contests
    for p in platforms:
        items = [r for r in problems if r['platform'] == p['id']]
        p['ac_count'] = sum(1 for r in items if r.get('status') == 'AC')
        p['record_count'] = len(items)
    contests.sort(key=lambda c: c.get('date') or '', reverse=True)
    return {'schema': 2, 'generated_at': now_iso(), 'owner': config.get('owner', 'lost.in'),
            'platforms': platforms, 'problems': problems, 'contests': contests, 'ratings': ratings}


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     suffix='.json.tmp', delete=False) as temp:
        json.dump(data, temp, ensure_ascii=False, indent=2)
        temp.write('\n')
        temp_path = Path(temp.name)
    temp_path.replace(path)


def public_snapshot(config,local_problems,local_contests):
    data=get_json('https://www.djtu.com.cn/api/algoarchive',attempts=1)
    if data.get('schema')!=2 or any(not isinstance(data.get(k),list) for k in ['platforms','problems','contests']):
        raise ValueError('Invalid public snapshot')
    info={p['id']:p for p in data['platforms']}
    expected={p['id']:str(p['handle']) for p in config.get('platforms',[]) if p.get('mode')=='auto' and p.get('handle')}
    if data.get('owner')!=config.get('owner') or any(str(info.get(k,{}).get('handle'))!=v for k,v in expected.items()):
        raise ValueError('Public snapshot account mismatch')
    result=assemble(config,data,local_problems,local_contests,offline=True)
    for p in result['platforms']:
        if p['id'] in expected:
            for key in ['sync_status','error','last_ok','cursor','history_complete']:p[key]=info[p['id']].get(key)
    if data.get('tag_sync'):
        result['tag_sync']={**data['tag_sync'],'total':len(result['problems']),'tagged':sum(bool(p.get('tags')) for p in result['problems'])}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Aggregate OJ problems and contest archives')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--manual', type=Path, default=MANUAL)
    parser.add_argument('--contests', type=Path, default=MANUAL_CONTESTS)
    parser.add_argument('--offline', action='store_true', help='Build entirely from existing API cache and CSV')
    parser.add_argument('--prefer-live',action='store_true',help='Prefer the account-verified public API snapshot; fall back to source adapters')
    args = parser.parse_args(argv)
    config = read_json(args.config, {})
    if not config.get('platforms'):
        parser.error('Config must include a nonempty platforms array')
    old = read_json(args.output, {'problems': [], 'contests': [], 'ratings': {}, 'platforms': []})
    problems,contests=manual_problems(args.manual),manual_contests(args.contests)
    result=None
    if args.prefer_live and not args.offline:
        try:result=public_snapshot(config,problems,contests)
        except Exception:print('warning: public snapshot unavailable; using source adapters and retained cache',file=sys.stderr)
    if result is None:result=assemble(config,old,problems,contests,offline=args.offline)
    atomic_json(args.output, result)
    total = sum(p['ac_count'] for p in result['platforms'])
    print(f'Wrote {args.output}: {total} AC across {len(result["platforms"])} OJs')
    for p in result['platforms']:
        if p['mode'] == 'auto':
            print(f'  {p["id"]}: {p["sync_status"]}, {p["ac_count"]} AC')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
