"""Tests for read-only AlgoArchive bridge and non-invasive native Butterfly builder."""
import importlib.util
from contextlib import closing
import sqlite3
import tempfile
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / 'tools/algo' if (BASE / 'tools/algo').is_dir() else BASE / 'scripts'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


builder = load(SCRIPTS/'build_butterfly_archive.py', 'builder')
bridge = load(SCRIPTS/'export_algoarchive.py', 'bridge')


class IntegrationTests(unittest.TestCase):
    def test_build_is_native_and_preserves_sidebar(self):
        base = '''<html><head><title>Template | lost.in</title></head><body>
<nav><ul><li><a class="site-page child" href="/Tt_link/">补题</a></li></ul></nav>
<main class="layout" id="content-inner"><div id="page"><div class="top-img"></div><div class="container" id="article-container"></div></div><div class="aside-content" id="aside-content">EXISTING SIDEBAR</div></main>
<h1 id="site-title">Template</h1><footer id="footer">EXISTING FOOTER</footer></body></html>'''
        result=builder.patch_template(base)
        self.assertIn('EXISTING SIDEBAR',result)
        self.assertIn('EXISTING FOOTER',result)
        self.assertIn('href="/algo/"',result)
        self.assertIn('<section id="aa-root"',result)
        self.assertIn('href="/algo/archive.css',result)
        self.assertIn('src="/algo/archive.js',result)
        self.assertIn('<title>算法档案 | lost.in</title>',result)
        self.assertIn('<h1 id="site-title">算法档案</h1>',result)
        self.assertEqual(result.count('id="article-container"'),1)
        self.assertEqual(builder.insert_nav(result),result)

    def test_build_generates_from_actual_site_page(self):
        with tempfile.TemporaryDirectory() as t:
            site=Path(t)
            (site/'Template').mkdir()
            (site/'Template/index.html').write_text('<html><head><title>Template | lost.in</title></head><body><div class="container" id="article-container"></div></body></html>',encoding='utf-8')
            created,changed=builder.build(site)
            self.assertEqual((created,changed),(1,0))
            self.assertIn('id="aa-root"',(site/'algo/index.html').read_text(encoding='utf-8'))

    def test_export_private_code_is_opt_in(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)
            dbpath=directory/'archive.sqlite3'
            path='codes/'+'a'*32+'.cpp'
            (directory/'codes').mkdir()
            (directory/path).write_text('int secret_code=42;',encoding='utf-8')
            with closing(sqlite3.connect(dbpath)) as db:
                db.executescript('''CREATE TABLE problems(id text,platform text,number text,name text,url text,language text,contest_id text,algorithm_id text,global_order int,algorithm_order int,code_path text,updated_at text);
                CREATE TABLE contests(id text,platform text,title text,url text,updated_at text);
                CREATE TABLE algorithms(id text,name text,category text,description text,updated_at text);
                CREATE TABLE algorithm_snippets(id text,algorithm_id text,title text,language text,code_path text,updated_at text);
                CREATE TABLE algorithm_links(id text,algorithm_id text,title text,url text);
                ''')
                db.execute('INSERT INTO problems VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('u1','codeforces','1902D','Robot Queries','https://codeforces.com/problemset/problem/1902/D','cpp',None,None,1,1,path,'2026-10-29'))
                db.execute('INSERT INTO algorithms VALUES(?,?,?,?,?)',('a1','树状数组','数据结构','说明','2026-10-29'))
                db.commit()
            normal=bridge.export(dbpath)
            self.assertEqual(normal['problems'][0]['name'],'Robot Queries')
            self.assertNotIn('code',normal['problems'][0])
            self.assertEqual(normal['algorithms'][0]['name'],'树状数组')
            opt_in=bridge.export(dbpath,include_code=True)
            self.assertEqual(opt_in['problems'][0]['code'],'int secret_code=42;')
            self.assertIsNone(bridge.safe_code(directory,'../secret.txt'))


if __name__=='__main__':unittest.main()
