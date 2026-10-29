"""Independent public practice-link and contest-calendar adapters."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
from html import unescape
import json
import re
import sync_oj as sync

ROOT=sync.ROOT
OUTPUT=sync.ASSETS/'catalog.json'
WIKI='https://www.algowiki.cn'


def pages(path):
    result=[]
    for page in range(1,41):
        d=sync.get_json(WIKI+'/api/'+path+'?page='+str(page),attempts=1)
        if isinstance(d,list):return d
        if not isinstance(d.get('results'),list):raise ValueError('Public feed schema changed')
        result.extend(d['results'])
        if not d.get('next'):return result
    raise ValueError('Public feed exceeded bounded pagination')


def practice():
    rows=pages('competition-practice-links/')
    taxonomy=sync.get_json(WIKI+'/api/competition-practice-links/taxonomy/',attempts=1)
    out=[]
    for x in rows:
        links=[{'label':l.get('label',''),'url':l['url']} for l in x.get('practice_links',[]) if str(l.get('url','')).startswith(('https://','http://'))]
        out.append({'id':x['id'],'year':x.get('year'),'series':x.get('series'),'stage':x.get('stage'),
                    'name':x.get('short_name') or x.get('official_name'),'official_name':x.get('official_name'),
                    'organizer':x.get('organizer',''),'date':x.get('event_date') or x.get('event_date_text',''),
                    'links':links,'notes':x.get('practice_links_note',''),'updated_at':x.get('updated_at')})
    return {'items':out,'taxonomy':{k:taxonomy.get(k,[]) for k in ['years','series','stages']}}


def event(platform,pid,title,url,start,duration,kind='',fallback=False):
    if not start or duration is None:return None
    when=sync.dt.datetime.fromisoformat(str(start).replace('Z','+00:00'))
    duration=max(0,int(duration));end=when+sync.dt.timedelta(seconds=duration)
    now=sync.dt.datetime.now(sync.dt.timezone.utc)
    if end<now-sync.dt.timedelta(days=45) or when>now+sync.dt.timedelta(days=366):return None
    return {'id':str(pid),'platform':platform,'title':title,'url':url,'start':when.isoformat(),
            'end':end.isoformat(),'duration':duration,'kind':kind,'fallback':fallback}


def cf():
    rows=sync.cf_api('contest.list');out=[]
    for c in rows:
        title=c.get('name','');match=re.search(r'Div\.?\s*\d|Educational|ICPC',title,re.I)
        e=event('codeforces',c['id'],title,'https://codeforces.com/contest/'+str(c['id']),
                sync.iso_from_unix(c.get('startTimeSeconds')),c.get('durationSeconds'),match.group() if match else '')
        if e:out.append(e)
    return out


def atcoder():
    text=sync.get_text('https://atcoder.jp/contests/',attempts=1);parser=sync.SubmissionTable();parser.feed(text);out=[]
    for cells in parser.rows:
        if len(cells)<3:continue
        found=next(((c,l) for c in cells for l in c['links'] if re.fullmatch(r'/contests/[a-zA-Z0-9_-]+',l)),None)
        date=re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{4}',cells[0]['text'])
        if not found or not date:continue
        duration=re.search(r'(\d+):(\d{2})',cells[2]['text'])
        if not duration:continue
        c,path=found;pid=path.rsplit('/',1)[-1];start=sync.dt.datetime.strptime(date.group(),'%Y-%m-%d %H:%M:%S%z').isoformat()
        e=event('atcoder',pid,c['text'].lstrip('ⒶⒽ◉ '),'https://atcoder.jp'+path,start,(int(duration[1])*60+int(duration[2]))*60,pid[:3].upper())
        if e:out.append(e)
    if not out:raise ValueError('AtCoder calendar not available')
    return out


def nowcoder():
    text=sync.get_text('https://ac.nowcoder.com/acm/contest/vip-index',attempts=1);out=[];seen=set()
    for raw in re.findall(r'data-json="([^"]+)"',text):
        try:c=json.loads(unescape(unescape(raw)))
        except ValueError:continue
        if not c.get('contestId') or c['contestId'] in seen:continue
        seen.add(c['contestId']);title=c.get('contestName','');kind=next((v for v in ['小白月赛','周赛','练习赛','挑战赛','多校'] if v in title),'')
        e=event('nowcoder',c['contestId'],title,'https://ac.nowcoder.com/acm/contest/'+str(c['contestId']),
            sync.iso_from_unix(int(c.get('contestStartTime',0))/1000),int(c.get('contestEndTime',0)-c.get('contestStartTime',0))//1000,kind)
        if e:out.append(e)
    if not out:raise ValueError('Nowcoder calendar not available')
    return out


def luogu():
    out=[]
    # Anonymous calendar requests: never include private account contest listings.
    for page in range(1,4):
        d=sync.get_json('https://www.luogu.com.cn/contest/list?page='+str(page),attempts=1,headers={'x-lentille-request':'content-only'})
        listing=d.get('data',{}).get('contests',{});rows=listing.get('result')
        if not isinstance(rows,list):raise ValueError('Luogu calendar not available')
        for c in rows:
            title=c.get('name') or c.get('title','');kind=next((v for v in ['重现赛','月赛','邀请赛','省赛'] if v in title),'')
            e=event('luogu',c['id'],title,'https://www.luogu.com.cn/contest/'+str(c['id']),
                sync.iso_from_unix(c.get('startTime')),int(c.get('endTime',0)-c.get('startTime',0)),kind)
            if e:out.append(e)
        if not rows:break
    return out


def build(previous=None, fetchers=None):
    previous=previous or {};sources=dict(previous.get('sources') or {});events=[]
    practice_data=previous.get('practice') or {'items':[],'taxonomy':{}}
    fetchers=fetchers or {'practice':practice,'codeforces':cf,'atcoder':atcoder,'nowcoder':nowcoder,'luogu':luogu}
    failed=[]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures={name:ex.submit(fetch) for name,fetch in fetchers.items()}
        for name,future in futures.items():
            old=sources.get(name,{})
            try:
                value=future.result()
                if name=='practice':practice_data=value
                else:events.extend(value)
                sources[name]={'last_ok':sync.now_iso(),'error':''}
            except Exception:
                sources[name]={**old,'error':'来源暂时无法更新'}
                if name!='practice':
                    failed.append(name);events.extend(e for e in previous.get('events',[]) if e['platform']==name)
    if failed:
        try:
            for c in pages('competition-calendar/'):
                if c.get('source_site') not in failed:continue
                e=event(c['source_site'],c['source_id'],c['title'],c['url'],c.get('start_time'),c.get('duration_seconds'),fallback=True)
                if e:events.append(e)
        except Exception:pass
    by_id={}
    for e in events:
        k=e['platform']+':'+e['id']
        if k not in by_id or not e.get('fallback'):by_id[k]=e
    multi=sync.read_json(ROOT/'config/multischool.json',{'platforms':[]}).get('platforms',[])
    return {'schema':1,'generated_at':sync.now_iso(),'practice':practice_data,'events':list(by_id.values()),'sources':sources,'multischool':multi}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUTPUT);args=parser.parse_args()
    data=build(sync.read_json(args.output,{}));sync.atomic_json(args.output,data)
    print(f'Practice links: {len(data["practice"]["items"])}; calendar entries: {len(data["events"])}')
