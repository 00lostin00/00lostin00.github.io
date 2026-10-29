#!/usr/bin/env python3
"""Read-only, schema-aware bridge for AlgoArchive 2.x SQLite -> public JSON.

Independent bridge: uses the publicly documented SQLite schema, not AlgoArchive code.
By default never exports code, tests, avatar or config. Code requires opt-in.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import tempfile


def rows(db, table: str) -> list[dict]:
    if table not in {'problems', 'contests', 'algorithms', 'algorithm_snippets', 'algorithm_links'}:
        raise ValueError('Unknown table')
    if db.execute('SELECT name FROM sqlite_master WHERE type="table" AND name=?', (table,)).fetchone() is None:
        return []
    return [dict(row) for row in db.execute('SELECT * FROM ' + table)]


def safe_code(data_dir: Path, relative: str) -> str | None:
    # Refuse traversal and arbitrary files even if the DB was corrupted/modified.
    if not re.fullmatch(r'codes/[a-f0-9]{32}\.(cpp|py|java|txt)', relative or ''):
        return None
    file = data_dir / relative
    if not file.is_file() or file.stat().st_size > 200_000:
        return None
    try:
        return file.read_text(encoding='utf-8')
    except (UnicodeError, OSError):
        return None


def export(database: Path, include_code=False) -> dict:
    database = database.expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        problems = rows(db, 'problems')
        contests = rows(db, 'contests')
        algorithms = rows(db, 'algorithms')
        snippets = rows(db, 'algorithm_snippets')
        links = rows(db, 'algorithm_links')

    # Allowlist only deliberately public metadata; never export user settings, tests,
    # private local paths, backup archives or the SQLite file itself.
    out_problems = []
    for p in problems:
        item = {key: p.get(key) for key in (
            'id', 'platform', 'number', 'name', 'url', 'language', 'contest_id',
            'algorithm_id', 'global_order', 'algorithm_order', 'updated_at')}
        if include_code:
            item['code'] = safe_code(database.parent, p.get('code_path') or '')
        out_problems.append(item)
    out_snippets = []
    for s in snippets:
        item = {key: s.get(key) for key in ('id', 'algorithm_id', 'title', 'language', 'updated_at')}
        if include_code:
            item['code'] = safe_code(database.parent, s.get('code_path') or '')
        out_snippets.append(item)
    return {
        'schema': 1,
        'exported_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'has_code': bool(include_code),
        'problems': out_problems,
        'contests': [{key: c.get(key) for key in ('id', 'platform', 'title', 'url', 'updated_at')} for c in contests],
        'algorithms': [{key: a.get(key) for key in ('id', 'name', 'category', 'description', 'updated_at')} for a in algorithms],
        'snippets': out_snippets,
        'links': [{key: l.get(key) for key in ('id', 'algorithm_id', 'title', 'url')} for l in links],
    }


def write_atomic_json(path: Path, data: dict):
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, suffix='.json.tmp', delete=False) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
        temporary = Path(f.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description='只读导出 AlgoArchive SQLite 的公开比赛 / 题目 / 模板')
    parser.add_argument('--database', type=Path, default=Path.home() / 'AlgoArchive' / 'data' / 'archive.sqlite3')
    root = Path(__file__).resolve().parents[1]
    if root.name == 'tools':
        root = root.parent
    assets = root / 'source' / 'algo' if (root / 'source' / 'algo').is_dir() else root / 'algo'
    parser.add_argument('--output', type=Path, default=assets / 'archive.json')
    parser.add_argument('--include-code', action='store_true', help='明确同意公开全部题目和模板的本地源代码')
    args = parser.parse_args()
    data = export(args.database, args.include_code)
    write_atomic_json(args.output, data)
    print(f'只读导出：{len(data["problems"])} 题、{len(data["contests"])} 比赛、{len(data["algorithms"])} 算法；源代码公开：{data["has_code"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
