#!/usr/bin/env python3
"""Read-only, fixed-account OJ API. Public requests cannot select URLs/accounts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit
import sync_oj as sync
import sync_catalog
from tag_sync import TagState


class ArchiveState:
    def __init__(self, config, output, interval=60, tags=None):
        self.config=Path(config);self.output=Path(output);self.interval=max(60,interval)
        self.lock=threading.Lock();self.updating=False;self.last_attempt=0;self.error=None
        self.data=sync.read_json(self.output, {'schema':2,'platforms':[],'problems':[],'contests':[],'ratings':{}})
        self.tags=tags

    def request_refresh(self):
        with self.lock:
            if self.updating or time.monotonic()-self.last_attempt<self.interval:return False
            self.updating=True;self.last_attempt=time.monotonic()
        threading.Thread(target=self.refresh,daemon=True).start()
        return True

    def refresh(self):
        try:
            config=sync.read_json(self.config,{})
            if not config.get('platforms'):raise ValueError('Missing platform configuration')
            with self.lock:previous=self.data
            root=self.config.parent.parent
            result=sync.assemble(config,previous,sync.manual_problems(root/'data/manual.csv'),sync.manual_contests(root/'data/contests.csv'))
            sync.atomic_json(self.output,result)
            with self.lock:self.data=result;self.error=None
        except Exception as exc:
            # Never log credentials, headers, or arbitrary upstream response bodies.
            with self.lock:self.error=type(exc).__name__
        finally:
            with self.lock:self.updating=False

    def snapshot(self):
        with self.lock:
            data={**self.data,'live':{'refreshing':self.updating,'cache_seconds':self.interval,
                'served_at':sync.now_iso(),'error':self.error}}
        return self.tags.overlay(data) if self.tags else data


class CatalogState(ArchiveState):
    def __init__(self, config, output):
        super().__init__(config,output,300)
        if self.data.get('schema')!=1:self.data={'schema':1,'events':[],'practice':{'items':[]},'sources':{}}

    def refresh(self):
        try:
            result=sync_catalog.build(self.data);sync.atomic_json(self.output,result)
            with self.lock:self.data=result;self.error=None
        except Exception as exc:
            with self.lock:self.error=type(exc).__name__
        finally:
            with self.lock:self.updating=False


def make_handler(state, origins, preview=None, catalog=None):
    class Handler(SimpleHTTPRequestHandler if preview else BaseHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            if preview:kwargs['directory']=str(preview)
            super().__init__(*args,**kwargs)

        def do_GET(self):
            route=urlsplit(self.path).path
            if route=='/health':self.respond({'ok':True});return
            if route in ['/api/archive','/api/catalog']:
                origin=self.headers.get('Origin')
                if origin and origin not in origins:self.respond({'error':'origin not allowed'},403);return
                selected=catalog if route=='/api/catalog' else state
                if selected is None:self.respond({'error':'not available'},404);return
                selected.request_refresh();self.respond(selected.snapshot());return
            if preview and route=='/algo/live.json':self.respond({'schema':1,'endpoint':'/api/archive','catalog_endpoint':'/api/catalog','refresh_seconds':state.interval});return
            if preview:return super().do_GET()
            self.respond({'error':'not found'},404)

        def do_OPTIONS(self):
            origin=self.headers.get('Origin')
            if origin and origin not in origins:self.respond({'error':'origin not allowed'},403);return
            self.send_response(204);self.cors();self.end_headers()

        def cors(self):
            origin=self.headers.get('Origin')
            if origin in origins:
                self.send_header('Access-Control-Allow-Origin',origin)
                self.send_header('Vary','Origin')
            self.send_header('Access-Control-Allow-Methods','GET, OPTIONS')
            self.send_header('X-Content-Type-Options','nosniff')

        def respond(self,data,status=200):
            payload=json.dumps(data,ensure_ascii=False).encode('utf8')
            self.send_response(status);self.cors()
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(payload)

        def log_message(self,*_):pass
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--config',type=Path,default=sync.CONFIG)
    parser.add_argument('--output',type=Path,default=sync.OUTPUT)
    parser.add_argument('--interval',type=int,default=60)
    parser.add_argument('--preview',type=Path)
    args=parser.parse_args()
    origins=set(os.environ.get('ALGO_ALLOWED_ORIGINS','https://00lostin00.github.io,http://127.0.0.1:4010,http://localhost:4010,http://127.0.0.1:4011,http://localhost:4011').split(','))
    tags=TagState(args.config.parent/'tag_aliases.json',args.output,args.output.parent/'tags.json')
    state=ArchiveState(args.config,args.output,args.interval,tags=tags)
    catalog=CatalogState(args.config,args.output.parent/'catalog.json')
    server=ThreadingHTTPServer((args.host,args.port),make_handler(state,origins,args.preview,catalog))
    state.request_refresh()
    catalog.request_refresh();tags.start()
    print(f'Archive API listening on {args.host}:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
