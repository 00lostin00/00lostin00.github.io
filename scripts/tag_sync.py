"""Continuously refresh public problem metadata and normalize algorithm tags."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import threading
import time
from html import unescape
import sync_oj as sync


def key(value):
    return re.sub(r'\s+',' ',str(value).replace('\ufeff','').strip().lower())


class Normalizer:
    def __init__(self, config, taxonomy=None):
        self.ids=config.get('luogu_ids',{});self.aliases={key(k):v for k,v in config.get('aliases',{}).items()}
        self.taxonomy={str(t['id']):t for t in taxonomy or [] if t.get('type')==2}
        for number,t in self.taxonomy.items():
            if number in self.ids:self.aliases[key(t['name'])]=self.ids[number]
        self.compact={re.sub(r'\s+','',k):v for k,v in self.aliases.items()}

    def one(self, value):
        if isinstance(value,int) or str(value).isdigit():return self.ids.get(str(value))
        text=key(value)
        if text in self.aliases:return self.aliases[text]
        if re.sub(r'\s+','',text) in self.compact:return self.compact[re.sub(r'\s+','',text)]
        if re.search('[\u3400-\u9fff]',text):return None
        return text if text else None

    def tags(self, values):
        return sorted({result for value in values or [] if (result:=self.one(value))})


class TagState:
    def __init__(self, config, records, output):
        self.config=Path(config);self.records=Path(records);self.output=Path(output)
        self.data=sync.read_json(output,{'schema':1,'entries':{},'taxonomy':[],'scans':{},'updated_at':None})
        self.lock=threading.RLock();self.stop=threading.Event()
        self.errors={}
        self.normalizer=Normalizer(sync.read_json(config,{}),self.data.get('taxonomy',[]))
        for entry in self.data.get('entries',{}).values():
            entry['tags']=self.normalizer.tags(entry.get('raw_tags',entry.get('tags',[])))

    def wanted(self,platform):
        return [p for p in sync.read_json(self.records,{}).get('problems',[]) if p.get('platform')==platform]

    def save(self):
        with self.lock:
            self.data['updated_at']=sync.now_iso();sync.atomic_json(self.output,self.data)

    def put(self,platform,pid,tags,title='',source='',status='ok'):
        with self.lock:
            self.data['entries'][platform+':'+str(pid).lower()]={'tags':self.normalizer.tags(tags),
                'raw_tags':tags,'title':title,'source':source,'status':status,'checked_at':sync.now_iso()}

    def overlay(self, data):
        with self.lock:
            problems=[];complete=0;unavailable=0
            for p in data.get('problems',[]):
                meta=self.data['entries'].get(p['platform']+':'+str(p['id']).lower())
                if not meta and p['platform']=='luogu' and str(p['id']).startswith('CF'):
                    meta=self.data['entries'].get('codeforces:'+p['id'][2:].lower())
                tags=self.normalizer.tags(p.get('raw_tags',p.get('tags',[])) if p['platform']=='acwing' else p.get('tags',[]))
                if meta or p.get('tag_source'):complete+=1
                if meta:
                    unavailable+=meta['status']=='unavailable'
                    if meta['status']=='ok' and p['platform']!='acwing':tags=meta['tags']
                problems.append({**p,'tags':tags,**({'title':meta['title']} if meta and meta.get('title') else {}),
                    **({'first_accepted_at':min(v for v in [p.get('first_accepted_at'),meta['first_accepted_at']] if v),
                        'accepted_at':max(v for v in [p.get('accepted_at'),meta.get('accepted_at')] if v)} if meta and meta.get('first_accepted_at') else {}),
                    **({'tag_source':meta.get('source'),'tags_updated_at':meta.get('checked_at')} if meta else {})})
            metadata={'completed':complete,'total':len(problems),'tagged':sum(bool(p['tags']) for p in problems),
                      'unavailable':unavailable,'updated_at':self.data.get('updated_at'),'refresh_seconds':900,'errors':dict(self.errors)}
            return {**data,'problems':problems,'tag_sync':metadata,
                    'generated_at':max(data.get('generated_at') or '',self.data.get('updated_at') or '')}

    def start(self):
        for platform in ['codeforces','luogu','nowcoder','atcoder','acwing']:
            threading.Thread(target=self.run,args=(platform,),daemon=True).start()

    def run(self, platform):
        while not self.stop.is_set():
            try:
                if platform=='codeforces':self.cf()
                elif platform=='luogu':self.luogu()
                elif platform=='acwing':self.acwing()
                else:self.individual(platform)
                self.errors.pop(platform,None)
            except Exception as exc:
                self.errors[platform]=type(exc).__name__
                self.stop.wait(60)
            self.stop.wait(900 if platform=='codeforces' else 8)

    def cf(self):
        result=sync.cf_api('problemset.problems');wanted={str(p['id']).lower() for p in self.wanted('codeforces')}
        for p in result.get('problems',[]):
            pid=str(p.get('contestId',''))+str(p.get('index',''))
            if pid.lower() in wanted:self.put('codeforces',pid,p.get('tags',[]),p.get('name',''),'Codeforces public API')
        self.save()

    def acwing(self):
        import sync_acwing
        data=sync.read_json(self.records,{})
        handle=next((p.get('handle') for p in data.get('platforms',[]) if p['id']=='acwing'),None)
        if not handle:return
        for p in self.due('acwing',self.wanted('acwing'),10):
            k='acwing:'+str(p['id']).lower()
            with self.lock:old=dict(self.data['entries'].get(k,{}))
            try:
                values=sync_acwing.dates(p,handle,bool(old.get('history_complete')))
                if old.get('first_accepted_at'):values['first_accepted_at']=min(values['first_accepted_at'],old['first_accepted_at'])
                self.put('acwing',p['id'],p.get('tags',[]),source='AcWing authorized problem list and own submission timestamps')
                with self.lock:self.data['entries'][k].update(values)
            except Exception:
                if old:
                    with self.lock:self.data['entries'][k]['checked_at']=sync.now_iso()
                else:self.put('acwing',p['id'],p.get('tags',[]),source='AcWing authorized problem list',status='unavailable')
            self.save()

    def luogu(self):
        headers={**sync.session_headers('luogu'),'x-lentille-request':'content-only'}
        if not self.data.get('taxonomy'):
            taxonomy=sync.get_json('https://www.luogu.com.cn/_lfe/tags',attempts=1,headers=headers)['tags']
            with self.lock:
                self.data['taxonomy']=[t for t in taxonomy if t.get('type')==2]
                self.normalizer=Normalizer(sync.read_json(self.config,{}),self.data['taxonomy'])
        wanted={p['id']:p for p in self.wanted('luogu')}
        # The public P/B lists contain tags for 50 problems per request.
        for kind in ['P','B']:
            ids={pid for pid in wanted if re.fullmatch(kind+r'\d+',pid)}
            if not ids:continue
            scan=self.data.setdefault('scans',{}).setdefault(kind,{'page':1,'finished':False,'cycle':0})
            if scan['finished']:
                if time.time()-scan.get('cycle',0)<900:continue
                scan.update(page=1,finished=False)
            for _ in range(8 if kind=='P' else 2):
                page=scan['page'];d=sync.get_json('https://www.luogu.com.cn/problem/list?type='+kind+'&page='+str(page),attempts=1,headers=headers)
                listing=d.get('data',{}).get('problems',{});rows=listing.get('result')
                if not isinstance(rows,list):raise ValueError('Problem list schema changed')
                for p in rows:
                    if p.get('pid') in ids:self.put('luogu',p['pid'],p.get('tags',[]),p.get('name') or p.get('title',''),'Luogu public taxonomy')
                scan['page']+=1;self.save()
                max_wanted=max(int(pid[1:]) for pid in ids)
                beyond=rows and min(int(p['pid'][1:]) for p in rows if re.fullmatch(kind+r'\d+',p.get('pid',''))) > max_wanted
                if not rows or page*listing.get('perPage',50)>=listing.get('count',10**9) or beyond:
                    scan.update(finished=True,cycle=time.time());break
        # Private/custom problems are queried only with the user's authorized session.
        extra=[p for p in wanted.values() if not re.fullmatch(r'(P|B|CF)\d+[A-Za-z0-9]*',p['id'])]
        for p in self.due('luogu',extra,3):self.single_luogu(p['id'],'luogu',p['id'])

    def due(self,platform,problems,limit):
        now=time.time();items=[]
        with self.lock:
            for p in problems:
                meta=self.data['entries'].get(platform+':'+str(p['id']).lower())
                age=0
                if meta:
                    try:age=now-sync.dt.datetime.fromisoformat(meta['checked_at'].replace('Z','+00:00')).timestamp()
                    except ValueError:age=10**9
                if not meta or age>(3600 if meta['status']=='unavailable' else 900):items.append((bool(meta),p))
        return [p for _,p in sorted(items,key=lambda x:x[0])[:limit]]

    def single_luogu(self,pid,platform,original):
        try:
            d=sync.get_json('https://www.luogu.com.cn/problem/'+sync.quote(pid),attempts=1,
                headers={**sync.session_headers('luogu'),'x-lentille-request':'content-only'})
            p=d.get('data',{}).get('problem')
            if not isinstance(p,dict):raise ValueError('No public problem metadata')
            self.put(platform,original,p.get('tags',[]),p.get('name') or p.get('title',''),'Luogu mirror' if platform!='luogu' else 'Luogu public taxonomy')
        except Exception:self.put(platform,original,[],source='Luogu public taxonomy',status='unavailable')
        self.save()

    def individual(self,platform):
        for p in self.due(platform,self.wanted(platform),10):
            if platform=='atcoder':self.single_luogu('AT_'+str(p['id']),platform,p['id']);continue
            try:
                text=sync.get_text('https://ac.nowcoder.com/acm/problem/list?keyword='+sync.quote(str(p['id'])),attempts=1)
                row=next((r for r in re.findall(r'<tr\b[^>]*>.*?</tr>',text,re.S) if '/acm/problem/'+str(p['id'])+'"' in r),None)
                if not row:raise ValueError('No matching problem')
                raw=[unescape(re.sub('<[^>]+>','',t)).strip() for t in re.findall(r'<a\b[^>]*class="[^"]*\bjs-tag\b[^"]*"[^>]*>(.*?)</a>',row,re.S)]
                self.put(platform,p['id'],raw,source='Nowcoder problem bank')
            except Exception:self.put(platform,p['id'],[],source='Nowcoder problem bank',status='unavailable')
            self.save()
