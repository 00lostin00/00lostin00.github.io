import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools/algo' if (BASE / 'tools/algo').is_dir() else BASE / 'scripts'))
import sync_oj as s
from build_butterfly_archive import insert_nav


class SyncTests(unittest.TestCase):
    def test_short_lived_cookie_can_rotate_without_losing_login(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/start':
                    self.send_response(302);self.send_header('Set-Cookie','C3VK=new; Path=/');self.send_header('Location','/target');self.end_headers();return
                cookie=self.headers.get('Cookie','')
                payload=json.dumps({'rotated':'C3VK=new' in cookie,'login':'session=dummy' in cookie}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(payload)
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            headers={'Cookie':'session=dummy; C3VK=old'}
            for route in ['/start','/target']:
                result=s.get_json(base+route,headers=headers)
                self.assertTrue(result['rotated']);self.assertTrue(result['login'])
        finally:server.shutdown();server.server_close();thread.join()

    def test_private_cookie_format_is_validated_without_echoing_its_value(self):
        with patch.dict(os.environ,{'LUOGU_COOKIE':'dummy-invalid-secret'}):
            with self.assertRaises(ValueError) as error:s.session_headers('luogu')
            self.assertNotIn('dummy-invalid-secret',str(error.exception))
        with patch.dict(os.environ,{'LUOGU_COOKIE':'Cookie: session=dummy; name=value'}):
            self.assertEqual(s.session_headers('luogu')['Cookie'],'session=dummy; name=value')

    def test_codeforces_ac_and_gym_url(self):
        a = s.cf_problem({'verdict': 'OK', 'problem': {'contestId': 1907, 'index': 'D', 'name': 'Jump', 'rating': 1800, 'tags': ['binary search']}, 'creationTimeSeconds': 1000})
        self.assertEqual(a['id'], '1907D')
        self.assertEqual(a['rating'], 1800)
        self.assertEqual(a['status'], 'AC')
        self.assertIsNone(s.cf_problem({'verdict': 'WRONG_ANSWER', 'problem': {'contestId': 1, 'index': 'A'}}))
        self.assertIn('/gym/100500/problem/C', s.cf_problem({'verdict': 'OK', 'problem': {'contestId': 100500, 'index': 'C'}})['url'])

    def test_merge_deduplicates_and_keeps_latest(self):
        base = {'platform': 'codeforces', 'id': '1907D', 'status': 'AC', 'accepted_at': '2025-01-01T00:00:00Z'}
        later = {**base, 'accepted_at': '2026-01-01T00:00:00Z'}
        result = s.merge_problems([base], [later])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['accepted_at'], later['accepted_at'])

    def test_first_ac_survives_later_resubmission(self):
        first={'platform':'codeforces','id':'1A','status':'AC','accepted_at':'2020-01-01T00:00:00Z','first_accepted_at':'2020-01-01T00:00:00Z'}
        late={**first,'accepted_at':'2026-01-01T00:00:00Z','first_accepted_at':'2026-01-01T00:00:00Z'}
        result=s.merge_problems([late],[first])[0]
        self.assertEqual(result['first_accepted_at'],first['first_accepted_at'])
        self.assertEqual(result['accepted_at'],late['accepted_at'])

    def test_nowcoder_visible_submission_dates(self):
        html='<table><tr><td><a href="/acm/problem/123">题目</a></td><td>答案正确</td><td>2026-01-01 01:30:00</td></tr><tr><td><a href="/acm/problem/456">错误题</a></td><td>答案错误</td><td>2026-01-01 01:30:00</td></tr></table>'
        records,count=s.html_problems(html,'nowcoder')
        self.assertEqual(count,2);self.assertEqual(len(records),1)
        self.assertEqual(records[0]['first_accepted_at'],'2025-12-31T17:30:00Z')

    def test_problem_title_cannot_be_mistaken_for_an_accepted_verdict(self):
        html='<table><tr><td><a href="/problem/1">Accepted</a></td><td>Wrong Answer</td></tr></table>'
        records,_=s.html_problems(html,'qoj')
        self.assertEqual(records,[])

    def test_luogu_full_history_and_incremental_refresh(self):
        def row(number,pid,when):return {'id':number,'user':{'uid':452262},'status':12,'submitTime':when,'problem':{'pid':pid,'title':pid}}
        batches=[{'data':{'records':{'count':3,'result':[row(3,'P1',300),row(2,'P2',200)]}}},
                 {'data':{'records':{'count':3,'result':[row(1,'P1',100)]}}}]
        with patch.object(s,'get_json',side_effect=batches) as fetch:
            result=s.pull_luogu('452262',{},sleep=lambda _:None)
            self.assertEqual(fetch.call_count,2)
        self.assertTrue(result['history_complete']);self.assertEqual(result['cursor'],3)
        self.assertEqual(len(result['problems']),2)
        self.assertEqual(next(p for p in result['problems'] if p['id']=='P1')['first_accepted_at'],s.iso_from_unix(100))
        previous={'platforms':[{'id':'luogu','history_complete':True,'cursor':3}],'problems':result['problems']}
        with patch.object(s,'get_json',return_value={'data':{'records':{'count':4,'result':[row(4,'P3',400),row(3,'P1',300)]}}}) as fetch:
            update=s.pull_luogu('452262',previous,sleep=lambda _:None)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(update['cursor'],4);self.assertEqual(len(update['problems']),3)

    def test_manual_overlay_does_not_downgrade_ac(self):
        source = {'platform': 'codeforces', 'id': '1800A', 'title': 'Title', 'status': 'AC', 'tags': ['dp'], 'rating': 1600, 'source': 'api'}
        manual = {**source, 'status': 'TODO', 'notes': 'revise', 'tags': ['tree'], 'source': 'manual'}
        result = s.combine_auto_manual([source], [manual])
        self.assertEqual(result[0]['status'], 'AC')
        self.assertEqual(result[0]['notes'], 'revise')
        self.assertEqual(set(result[0]['tags']), {'dp', 'tree'})

    def test_platform_extension_and_preservation_on_failure(self):
        old = {'problems': [{'platform':'codeforces','id':'1A','status':'AC','source':'api','accepted_at':None}], 'contests':[], 'ratings':{}, 'platforms': [{'id':'codeforces','last_ok':'2026-01-01','cursor':None}]}
        config = {'owner':'lost.in','platforms':[{'id':'codeforces','handle':'lost.in','mode':'auto'}, {'id':'qoj','mode':'manual'}]}
        def fail(*_): raise RuntimeError('API offline')
        manual = [{'platform':'school-oj','id':'A100','status':'AC','source':'manual'}]
        result = s.assemble(config, old, manual, [], pulls={'codeforces':fail})
        self.assertEqual(result['platforms'][0]['sync_status'], 'error')
        self.assertEqual(len(result['problems']),2)
        self.assertIn('school-oj',[p['id'] for p in result['platforms']])

    def test_authorization_failure_is_explicit_and_preserves_known_records(self):
        previous={'problems':[{'platform':'qoj','id':'123','status':'AC','source':'api'}]}
        config={'platforms':[{'id':'qoj','mode':'auto','handle':'lostin'}]}
        def denied(*_):raise RuntimeError('upstream unavailable (HTTP 403)')
        result=s.assemble(config,previous,[],[],pulls={'qoj':denied})
        self.assertEqual(result['platforms'][0]['sync_status'],'blocked')
        self.assertEqual(result['problems'][0]['id'],'123')

    def test_manual_csv_read_and_write(self):
        with tempfile.TemporaryDirectory() as d:
            csvpath=Path(d)/'records.csv'; csvpath.write_text('platform,id,title,url,status,rating,level,tags,accepted_at,notes\nqoj,123,My Task,https://qoj.ac/problem/123,AC,,,dp;dfs,2026-10-01,review\n',encoding='utf-8')
            rows=s.manual_problems(csvpath)
            self.assertEqual(rows[0]['tags'], ['dp','dfs'])
            output=Path(d)/'out.json';s.atomic_json(output,{'problems':rows})
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['problems'][0]['id'],'123')

    def test_atcoder_normalizer(self):
        p = s.ac_problem({'result':'AC','problem_id':'abc123_c','contest_id':'abc123','epoch_second':1000},{'abc123_c':'Task C'})
        self.assertEqual(p['level'],'C')
        self.assertEqual(p['url'],'https://atcoder.jp/contests/abc123/tasks/abc123_c')

    def test_butterfly_menu_patch_idempotent(self):
        original='<ul><li><a class="site-page child" href="/Tt_link/"><span>补题链接</span></a></li></ul>'
        updated=insert_nav(original);self.assertEqual(updated.count('href="/algo/"'),1)
        again=insert_nav(updated)
        self.assertEqual(again,updated)


if __name__=='__main__': unittest.main()
