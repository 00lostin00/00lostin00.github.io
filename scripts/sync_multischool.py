"""Public multi-university problem sets; credentials never enter output JSON."""
from __future__ import annotations
import datetime as dt
import re
import time
import os
from html import unescape
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlsplit,urlencode
from http.cookiejar import CookieJar
import sync_oj as sync

HDU_ORIGIN='https://acm.hdu.edu.cn'


def hdu_discover():
    contests={}
    for page in range(3):
        text=sync.get_text(HDU_ORIGIN+'/contests/contest_list.php?page='+str(page),attempts=1)
        for path,title in re.findall(r'<a[^>]*href="(/contest/problems\?cid=\d+)"[^>]*>([^<]+)',text):
            cid=re.search(r'cid=(\d+)',path).group(1)
            contests[cid]={'id':cid,'url':HDU_ORIGIN+path,'title':unescape(title).strip()}
    if not contests:raise ValueError('HDU contest directory unavailable')
    return list(contests.values())


def hdu_problems(text,cid):
    if not re.search(r'<title>\s*Problems\s*</title>',text,re.I):
        raise ValueError('Authorized contest login unavailable')
    problems=[]
    for row in re.findall(r'<tr\b[^>]*>[\s\S]*?</tr>',text,re.I):
        cells=re.findall(r'<td\b[^>]*>([\s\S]*?)</td>',row,re.I)
        if len(cells)<3:continue
        match=re.search(r'href="(/contest/problem\?cid='+re.escape(str(cid))+r'&(?:amp;)?pid=(\d+))"[^>]*>([\s\S]*?)</a>',cells[2])
        if not match:continue
        path,pid,title=match.groups();number=int(pid)-1001
        problems.append({'id':pid,'index':chr(65+number) if 0<=number<26 else pid,
            'title':unescape(re.sub('<[^>]+>','',title)).strip(),'url':HDU_ORIGIN+unescape(path),
            'status':'AC' if re.search(r'(?:xlink:href|href)=["\']#done["\']',cells[0]) else 'TODO'})
    if not problems:raise ValueError('Incomplete authorized HDU problem list')
    return problems


class HDUClient:
    def __init__(self,username,password):
        self.username=username;self.password=password
        self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
        self.last_request=0

    def read(self,url,data=None):
        target=urlsplit(url)
        if target.scheme!='https' or target.hostname!='acm.hdu.edu.cn' or not target.path.startswith('/contest/'):
            raise ValueError('Unexpected contest login destination')
        delay=1.2-(time.monotonic()-self.last_request)
        if delay>0:time.sleep(delay)
        self.last_request=time.monotonic()
        with self.opener.open(Request(url,data=data,headers={'User-Agent':'Mozilla/5.0','Referer':url}),timeout=25) as response:
            final=urlsplit(response.url)
            if final.scheme!='https' or final.hostname!='acm.hdu.edu.cn':raise ValueError('Unexpected login redirect')
            return response.read().decode(response.headers.get_content_charset() or 'utf8'),response.url

    def problems(self,contest):
        text,url=self.read(contest['url'])
        if urlsplit(url).path=='/contest/login':
            data=urlencode({'username':self.username,'password':self.password}).encode()
            text,_=self.read(url,data=data)
        return hdu_problems(text,contest['id'])


def hdu_seasons(seasons,previous):
    previous={s['id']:s for s in previous or []};result=[];directory=None
    for season in seasons:
        old=previous.get(season['id'],{})
        item={k:season.get(k) for k in ['id','name','year','url']}
        prefix=season.get('credentials_env','');username=os.environ.get(prefix+'_USERNAME');password=os.environ.get(prefix+'_PASSWORD')
        item.update(account_configured=bool(username and password) or old.get('account_configured',False),contests=old.get('contests',[]),last_ok=old.get('last_ok'),sync_status='cached' if old.get('contests') else 'not_configured')
        if username and password:
            try:
                # Own progress is refreshed with the five-minute catalog cache.
                if directory is None:directory=hdu_discover()
                selected=[c for c in directory if str(season['year']) in c['title'] and season['match'] in c['title'] and re.search(r'[（(]\d+[）)]',c['title'])]
                if not selected:raise ValueError('Season directory unavailable')
                client=HDUClient(username,password);contests=[]
                old_contests={c['id']:c for c in item['contests']}
                for c in sorted(selected,key=lambda c:int(c['id'])):
                    try:contests.append({**c,'problems':client.problems(c),'last_ok':sync.now_iso(),'error':''})
                    except Exception:
                        if not contests:raise
                        contests.append({**c,'problems':old_contests.get(c['id'],{}).get('problems',[]),'last_ok':old_contests.get(c['id'],{}).get('last_ok'),'error':'该场比赛暂时无法更新'})
                item.update(contests=contests,last_ok=sync.now_iso(),sync_status='partial' if any(c['error'] for c in contests) else 'ok')
            except Exception:item['sync_status']='error'
        result.append(item)
    return result


def contest_problems(cid):
    payload=sync.get_json('https://ac.nowcoder.com/acm/contest/problem-list?id='+str(cid),attempts=1)
    data=payload.get('data') or {}
    if payload.get('code')!=0 or not isinstance(data.get('data'),list):
        raise ValueError('Public contest problems unavailable')
    rows=data['data'];info=data.get('basicInfo') or {}
    if not rows or info.get('pageCount',1)>1 or len(rows)!=info.get('problemCount',len(rows)):
        raise ValueError('Incomplete public contest problem list')
    return [{'id':str(p['problemId']),'index':str(p['index']),'title':p.get('title') or str(p['index']),
             'url':'https://ac.nowcoder.com/acm/contest/'+str(cid)+'/'+sync.quote(str(p['index']))}
            for p in rows]


def build(config,previous=None):
    previous={x['id']:x for x in previous or []};result=[]
    current=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).year
    for platform in config.get('platforms',[]):
        # Explicit public allowlist. Passwords/cookies are environment-only.
        item={k:platform.get(k) for k in ['id','name','url','account']}
        old=previous.get(item['id'],{});old_contests={str(c['id']):c for c in old.get('contests',[])}
        if item['id']=='nowcoder':
            contests=[]
            for year,ids in sorted(platform.get('years',{}).items(),reverse=True):
                if not current-2<=int(year)<=current:continue
                for round_no,cid in enumerate(ids,1):
                    cached=old_contests.get(str(cid),{})
                    c={'id':str(cid),'year':int(year),'round':round_no,'title':year+'牛客暑期多校训练营'+str(round_no),
                       'url':'https://ac.nowcoder.com/acm/contest/'+str(cid),
                       'problems':cached.get('problems',[]),'last_ok':cached.get('last_ok'),'error':''}
                    try:
                        stamp=dt.datetime.fromisoformat((c['last_ok'] or '1970-01-01T00:00:00+00:00').replace('Z','+00:00')).timestamp()
                        if not c['problems'] or time.time()-stamp>=900:
                            c['problems']=contest_problems(cid);c['last_ok']=sync.now_iso()
                    except Exception:c['error']='题单暂时无法更新，保留缓存'
                    contests.append(c)
            item['contests']=contests
        elif item['id']=='hdu':
            item['seasons']=hdu_seasons(platform.get('seasons',[]),old.get('seasons'))
        result.append(item)
    return result
