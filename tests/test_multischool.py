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
        with patch.object(multi,'contest_problems',side_effect=RuntimeError('offline')):
            rows=multi.build(config,previous)
        self.assertEqual(rows[0]['contests'][0]['problems'][0]['id'],'123')
        self.assertTrue(rows[0]['contests'][0]['error'])
        self.assertNotIn('password',rows[0])

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
