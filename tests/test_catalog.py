from pathlib import Path
import sys
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'tools/algo' if (BASE/'tools/algo').is_dir() else BASE/'scripts'))
import sync_catalog as c


class CatalogTests(unittest.TestCase):
    def test_practice_failure_keeps_previous_public_links(self):
        previous={'practice':{'items':[{'id':1,'name':'old'}]},'events':[],'sources':{}}
        def fail():raise RuntimeError('unavailable')
        with patch('sync_multischool.build',return_value=[]):
            result=c.build(previous,fetchers={'practice':fail})
        self.assertEqual(result['practice']['items'][0]['name'],'old')
        self.assertTrue(result['sources']['practice']['error'])

    def test_event_time_zone_and_duration_are_explicit(self):
        start=(c.sync.dt.datetime.now(c.sync.dt.timezone.utc)+c.sync.dt.timedelta(days=2)).isoformat()
        event=c.event('atcoder','abc999','Test','https://atcoder.jp/contests/abc999',start,6000)
        self.assertEqual(event['duration'],6000)
        self.assertEqual((c.sync.dt.datetime.fromisoformat(event['end'])-c.sync.dt.datetime.fromisoformat(event['start'])).total_seconds(),6000)
