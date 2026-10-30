import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import json

BASE=Path(__file__).resolve().parents[1]
SCRIPTS=BASE/'tools/algo' if (BASE/'tools/algo').is_dir() else BASE/'scripts'
sys.path.insert(0,str(SCRIPTS))
import serve_archive as live


class LiveTests(unittest.TestCase):
    def test_concurrent_visitors_share_one_refresh_and_preserve_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir()
            config=root/'config/oj_sources.json';config.write_text('{"platforms":[{"id":"codeforces"}]}')
            output=root/'data.json';output.write_text('{"schema":2,"problems":[{"id":"old"}]}')
            state=live.ArchiveState(config,output,60)
            gate=threading.Event()
            def wait(*_):gate.wait(2);raise RuntimeError('offline')
            # A newly booted Linux runner may have less than 60 seconds of
            # monotonic uptime. The first request must never be rate limited.
            with patch.object(live.time,'monotonic',return_value=5),patch.object(live.sync,'assemble',side_effect=wait) as pull:
                self.assertTrue(state.request_refresh());self.assertFalse(state.request_refresh())
                self.assertEqual(state.snapshot()['problems'][0]['id'],'old')
                gate.set()
                import time
                for _ in range(50):
                    if not state.snapshot()['live']['refreshing']:break
                    time.sleep(.01)
                self.assertEqual(pull.call_count,1)
                self.assertEqual(state.snapshot()['live']['error'],'RuntimeError')
                self.assertFalse(state.request_refresh())
                with patch.object(live.time,'monotonic',return_value=65),patch.object(live.threading,'Thread') as worker:
                    self.assertTrue(state.request_refresh())
                    worker.return_value.start.assert_called_once()

    def test_cors_and_read_only_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=live.ArchiveState(Path(tmp)/'config.json',Path(tmp)/'data.json')
            with patch.object(state,'request_refresh'):
                server=ThreadingHTTPServer(('127.0.0.1',0),live.make_handler(state,{'https://00lostin00.github.io'}))
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    url=f'http://127.0.0.1:{server.server_port}/api/archive'
                    with urlopen(Request(url,headers={'Origin':'https://00lostin00.github.io'})) as r:
                        self.assertEqual(r.headers['Access-Control-Allow-Origin'],'https://00lostin00.github.io')
                        self.assertEqual(json.load(r)['schema'],2)
                    with self.assertRaises(HTTPError):urlopen(Request(url,headers={'Origin':'https://unrelated.invalid'}))
                finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
