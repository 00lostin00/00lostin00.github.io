from pathlib import Path
import sys
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'tools/algo' if (BASE/'tools/algo').is_dir() else BASE/'scripts'))
import sync_acwing as ac
from tag_sync import Normalizer


class AcWingTests(unittest.TestCase):
    def test_list_uses_verified_own_ac_marker_and_preserves_display_and_internal_ids(self):
        row='''<tr><td><span class="glyphicon-ok"></span></td><td><span>899</span></td>
        <td><a id="problem-title-903" href="/problem/content/903/">Edit &amp; distance</a></td>
        <td><div id="problem-keywords-903"></div><script>let keywords = "动态规划,DP".split(',');</script></td>
        <td><span>简单</span></td></tr>'''
        normal=Normalizer({'aliases':{'动态规划':'dp'}})
        rows=ac.parse_list(row,normal)
        self.assertEqual(rows[0]['id'],'899');self.assertEqual(rows[0]['content_id'],'903')
        self.assertEqual(rows[0]['tags'],['dp']);self.assertEqual(rows[0]['title'],'Edit & distance')
        self.assertIsNone(rows[0]['first_accepted_at'])
        self.assertEqual(ac.parse_list(row.replace('glyphicon-ok','glyphicon-remove'),normal),[])

    def test_wrong_or_missing_authorized_account_is_rejected(self):
        ac.owner('me_id: 374248,','374248')
        for text in ['me_id: 111,','<title>Login</title>']:
            with self.assertRaises(ValueError):ac.owner(text,'374248')

    def test_public_snapshot_verifies_accounts_and_preserves_live_status_and_manual_edits(self):
        config={'owner':'lost.in','platforms':[{'id':'acwing','name':'AcWing','handle':'374248','mode':'auto'}]}
        snapshot={'schema':2,'owner':'lost.in','platforms':[{'id':'acwing','handle':'374248','sync_status':'ok'}],
                  'problems':[{'id':'1','platform':'acwing','title':'A+B','status':'AC','source':'api','tags':['implementation']}],'contests':[]}
        with patch.object(ac.sync,'get_json',return_value=snapshot):
            result=ac.sync.public_snapshot(config,[{'id':'2','platform':'acwing','status':'TODO','source':'manual'}],[])
        self.assertEqual(len(result['problems']),2)
        self.assertEqual(result['platforms'][0]['sync_status'],'ok')
        snapshot['platforms'][0]['handle']='wrong account'
        with patch.object(ac.sync,'get_json',return_value=snapshot):
            with self.assertRaises(ValueError):ac.sync.public_snapshot(config,[],[])

    def test_submission_history_ignores_wrong_answers_and_retains_earliest_ac_across_pages(self):
        def row(date,status,n):return f'<tr><td><span title="{date}"></span></td><td><span id="submission-result-{n}">{status}</span></td></tr>'
        recent=row('2026-10-29 13:00:00','ACCEPTED',3)+'<a href="/problem/content/submission/903/2/">2</a>'
        old=row('2023-01-01 10:00:00','WRONG_ANSWER',1)+row('2024-01-01 10:00:00','ACCEPTED',2)
        with patch.object(ac,'read',side_effect=[recent,old]):d=ac.dates({'content_id':'903'},'374248')
        self.assertEqual(d['first_accepted_at'],'2024-01-01T02:00:00Z')
        self.assertEqual(d['accepted_at'],'2026-10-29T05:00:00Z')
