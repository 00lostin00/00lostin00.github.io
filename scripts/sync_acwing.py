"""Read the authorized account's accepted list and submission timestamps only."""
from __future__ import annotations
import datetime as dt
import json
import math
import re
import time
from html import unescape
import sync_oj as sync

ORIGIN='https://www.acwing.com'


def owner(text,handle):
    found=re.search(r'\bme_id\s*:\s*(\d+)',text)
    if not found or found.group(1)!=str(handle):
        raise ValueError('AcWing login is unavailable or belongs to a different configured account')


def read(path,handle):
    text=sync.get_text(ORIGIN+path,attempts=1,headers=sync.session_headers('acwing'))
    owner(text,handle)
    return text


def parse_list(text,normalizer):
    result=[]
    for row in re.findall(r'<tr\b[^>]*>[\s\S]*?</tr>',text,re.I):
        cells=re.findall(r'<td\b[^>]*>([\s\S]*?)</td>',row,re.I)
        if len(cells)<4 or 'glyphicon-ok' not in cells[0]:continue
        anchor=re.search(r'id="problem-title-\d+"[^>]*href="/problem/content/(\d+)/"[^>]*>([\s\S]*?)</a>',cells[2])
        if not anchor:continue
        content_id,title=anchor.groups();number=re.sub('<[^>]+>','',cells[1]).strip()
        if not number.isdigit():continue
        raw=[]
        for cell in cells:
            if 'problem-keywords-' not in cell:continue
            match=re.search(r'let keywords\s*=\s*("(?:\\.|[^"\\])*")',cell)
            if match:
                value=json.loads(match.group(1));raw=[unescape(x).strip() for x in re.split('[,，]',value) if x.strip()]
        level=re.sub('<[^>]+>','',cells[-1]).strip()
        result.append({'platform':'acwing','id':number,'content_id':content_id,
            'title':unescape(re.sub('<[^>]+>','',title)).strip(),'url':ORIGIN+'/problem/content/'+content_id+'/',
            'status':'AC','rating':None,'level':level,'tags':normalizer.tags(raw),'raw_tags':raw,
            'tag_source':'AcWing authorized problem list','source':'api','notes':'',
            'accepted_at':None,'first_accepted_at':None})
    return result


def pull(handle,previous):
    if not str(handle).isdigit():raise ValueError('AcWing requires a numeric account ID')
    from tag_sync import Normalizer
    aliases=sync.read_json(sync.CONFIG.parent/'tag_aliases.json',{})
    cache=sync.read_json(sync.OUTPUT.parent/'tags.json',{})
    normal=Normalizer(aliases,cache.get('taxonomy',[]))
    path='/problem/?show_algorithm_tags=1&show_accepted_problems=all'
    text=read(path,handle)
    count=re.search(r'show-accepted-problems-btn"\s+data-type="all"[^>]*>[\s\S]*?<span[^>]*>\s*(\d+)\s*</span>',text)
    if not count:raise ValueError('Cannot confirm AcWing accepted list')
    total=int(count.group(1));prior=next((p for p in previous.get('platforms',[]) if p.get('id')=='acwing'),{})
    cursor=prior.get('cursor') if isinstance(prior.get('cursor'),dict) else {}
    old=[p for p in previous.get('problems',[]) if p.get('platform')=='acwing' and p.get('source')=='api']
    if cursor.get('owner')==str(handle) and cursor.get('count')==total and len(old)==total and time.time()-cursor.get('checked_at',0)<900:
        return {'problems':old,'contests':[],'rating':{},'partial':False,'history_complete':True,'cursor':cursor}
    rows=parse_list(text,normal)
    for page in range(2,math.ceil(total/50)+1):
        rows.extend(parse_list(read('/problem/'+str(page)+'/?show_algorithm_tags=1&show_accepted_problems=all',handle),normal))
    by_id={p['id']:p for p in rows}
    if len(by_id)!=total:raise ValueError('AcWing accepted list is incomplete; previous records retained')
    old_by_id={p['id']:p for p in old} if prior.get('handle')==str(handle) else {}
    for pid,p in by_id.items():
        old_p=old_by_id.get(pid,{})
        for key in ['accepted_at','first_accepted_at']:
            if old_p.get(key):p[key]=old_p[key]
    return {'problems':list(by_id.values()),'contests':[],'rating':{},'partial':False,'history_complete':True,
            'cursor':{'owner':str(handle),'count':total,'checked_at':time.time()}}


def submission_times(text):
    dates=[]
    for row in re.findall(r'<tr\b[^>]*>[\s\S]*?</tr>',text,re.I):
        if not re.search(r'id="submission-result-\d+">\s*ACCEPTED\s*</span>',row):continue
        match=re.search(r'title="(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"',row)
        if match:
            dates.append(dt.datetime.strptime(match.group(1),'%Y-%m-%d %H:%M:%S').replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z'))
    return dates


def dates(problem,handle,already_complete=False):
    cid=problem['content_id'];path='/problem/content/submission/'+str(cid)+'/'
    text=read(path,handle);values=submission_times(text)
    pages=max([int(v) for v in re.findall(r'/problem/content/submission/'+re.escape(str(cid))+r'/(\d+)/',text)] or [1])
    if pages>40:raise ValueError('Submission history exceeds bounded scan')
    if not already_complete:
        for page in range(2,pages+1):values.extend(submission_times(read(path+str(page)+'/',handle)))
    if not values:raise ValueError('No confirmed accepted timestamp')
    return {'first_accepted_at':min(values),'accepted_at':max(values),'history_complete':True}
