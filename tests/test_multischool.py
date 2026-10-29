from pathlib import Path
import sys
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'tools/algo' if (BASE/'tools/algo').is_dir() else BASE/'scripts'))
import sync_multischool as multi
import sync_oj as sync


class MultischoolTests(unittest.TestCase):
    def test_public_problem_id_maps_to_contest_letter_not_anonymous_my_status(self):
        response={'code':0,'data':{'data':[{'problemId':123,'index':'A','title':'Test','myStatus':'未通过'}],
                                  'basicInfo':{'problemCount':1,'pageCount':1}}}
        with patch.object(sync,'get_json',return_value=response):
            rows=multi.contest_problems(10)
        self.assertEqual(rows,[{'id':'123','index':'A','title':'Test','url':'https://ac.nowcoder.com/acm/contest/10/A'}])
        self.assertNotIn('myStatus',rows[0])

    def test_failed_source_preserves_previous_problem_set_and_never_exports_secrets(self):
        year=str(multi.dt.datetime.now().year)
        config={'platforms':[{'id':'nowcoder','name':'test','account':'541540317','password':'private','years':{year:[10]}}]}
        previous=[{'id':'nowcoder','contests':[{'id':'10','problems':[{'id':'123','index':'A'}]}]}]
        with patch.object(multi,'contest_problems',side_effect=RuntimeError('offline')),patch.object(multi,'nowcoder_progress',side_effect=RuntimeError('offline')):
            rows=multi.build(config,previous)
        self.assertEqual(rows[0]['contests'][0]['problems'][0]['id'],'123')
        self.assertTrue(rows[0]['contests'][0]['error'])
        self.assertNotIn('password',rows[0])

    def test_contest_progress_includes_platform_resolved_team_and_paginates_first_ac(self):
        def response(page,stamp):return {'code':0,'data':{'basicInfo':{'contestId':133876,'searchUserName':'541540317','pageCount':2},
            'data':[{'userId':426671698,'isTeam':True,'problemId':319387,'index':'A','statusMessage':'答案正确','submitTime':stamp}]}}
        with patch.object(sync,'get_json',side_effect=[response(1,1784536727000),response(2,1784266406000)]) as fetch:
            progress=multi.nowcoder_progress(133876,'541540317')
        self.assertEqual(len(progress['accepted']),1)
        self.assertTrue(progress['is_team'])
        self.assertLess(progress['accepted'][0]['first_accepted_at'],progress['accepted'][0]['accepted_at'])
        self.assertEqual(fetch.call_count,2)
        self.assertIn('searchUserName=541540317',fetch.call_args.args[0])

    def test_unrelated_individual_and_unscoped_response_do_not_become_own_progress(self):
        response={'code':0,'data':{'basicInfo':{'contestId':10,'searchUserName':'541540317','pageCount':1},
            'data':[{'userId':999,'isTeam':False}]}}
        with patch.object(sync,'get_json',return_value=response):
            with self.assertRaises(ValueError):multi.nowcoder_progress(10,'541540317')
        response['data']['data']=[];response['data']['basicInfo']['searchUserName']=''
        with patch.object(sync,'get_json',return_value=response):
            with self.assertRaises(ValueError):multi.nowcoder_progress(10,'541540317')

    def test_removed_oj_is_not_restored_from_old_automatic_cache(self):
        config={'platforms':[{'id':'nowcoder','mode':'manual'}]}
        old={'problems':[{'id':'1','platform':'qoj','source':'api'}],
             'contests':[{'id':'1','platform':'qoj','source':'api'}],'ratings':{'qoj':{'current':100}}}
        result=sync.assemble(config,old,[],[],offline=True)
        self.assertEqual(result['problems'],[]);self.assertEqual(result['contests'],[])
        self.assertNotIn('qoj',result['ratings'])

    def test_cf_requests_explicit_english_names(self):
        with patch.object(sync,'get_json',return_value={'status':'OK','result':[]}) as fetch:
            sync.cf_api('problemset.problems')
        self.assertIn('lang=en',fetch.call_args.args[0])

    def test_hdu_uses_only_own_done_marker_not_global_accepted_statistics(self):
        text='''<title>Problems</title><table>
        <tr><td><svg><use xlink:href="#done" /></svg></td><td>1001</td><td><a href="/contest/problem?cid=1229&pid=1001">Passed</a></td><td>0%</td></tr>
        <tr><td></td><td>1002</td><td><a href="/contest/problem?cid=1229&pid=1002">Other</a></td><td>100% (999/999)</td></tr></table>'''
        rows=multi.hdu_problems(text,1229)
        self.assertEqual([(p['index'],p['status']) for p in rows],[('A','AC'),('B','TODO')])
        with self.assertRaises(ValueError):multi.hdu_problems('<title>Contest Login</title>',1229)
