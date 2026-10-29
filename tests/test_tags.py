import json
from pathlib import Path
import sys
import tempfile
import unittest
BASE=Path(__file__).resolve().parents[1]
SCRIPTS=BASE/'tools/algo' if (BASE/'tools/algo').is_dir() else BASE/'scripts'
sys.path.insert(0,str(SCRIPTS))
from tag_sync import Normalizer,TagState


class TagTests(unittest.TestCase):
    def test_english_aliases_and_chinese_synonyms_merge(self):
        config=json.loads((BASE/'config/tag_aliases.json').read_text(encoding='utf8'))
        normal=Normalizer(config,[{'id':3,'name':'动态规划 DP','type':2}])
        self.assertEqual(normal.tags(['数学','Math','mathematics','dynamic programming','动态规划 DP',3]),['dp','math'])
        self.assertEqual(normal.tags(['disjoint set union','并查集','DSU']),['dsu'])
        self.assertEqual(normal.tags(['二维前缀和','prefix sums','状态压缩DP','bitmask dp','主席树']),['bitmask dp','persistent segment trees','prefix sums'])
        self.assertEqual(len(config['luogu_ids']),262)
        self.assertFalse(any(__import__('re').search('[\u3400-\u9fff]',x) for x in config['luogu_ids'].values()))

    def test_overlay_keeps_provenance_and_does_not_invent_missing_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'aliases.json'
            config.write_text('{"aliases":{"数学":"math"}}',encoding='utf8')
            tags=TagState(config,root/'records.json',root/'tags.json')
            tags.put('nowcoder','1',['数学','math'],source='public metadata')
            original={'schema':2,'problems':[{'platform':'nowcoder','id':'1','tags':[]},{'platform':'qoj','id':'2','tags':[]}]}
            result=tags.overlay(original)
            self.assertEqual(result['problems'][0]['tags'],['math'])
            self.assertEqual(result['problems'][0]['tag_source'],'public metadata')
            self.assertEqual(result['problems'][1]['tags'],[])
            self.assertEqual(original['problems'][0]['tags'],[])

    def test_acwing_verified_history_enriches_dates_without_moving_first_ac_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tags=TagState(root/'aliases.json',root/'records.json',root/'tags.json')
            tags.put('acwing','1',['dp'])
            tags.data['entries']['acwing:1'].update(first_accepted_at='2024-01-01T00:00:00Z',accepted_at='2026-01-01T00:00:00Z')
            result=tags.overlay({'problems':[{'platform':'acwing','id':'1','first_accepted_at':'2023-01-01T00:00:00Z'}]})
            self.assertEqual(result['problems'][0]['first_accepted_at'],'2023-01-01T00:00:00Z')
            self.assertEqual(result['problems'][0]['accepted_at'],'2026-01-01T00:00:00Z')
