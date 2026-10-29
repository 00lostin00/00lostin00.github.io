#!/usr/bin/env python3
"""Create a native Butterfly page from *the site's own* generated page.

No copied upstream theme/AlgoArchive source code. Other page structures/styles are retained.
Run after hexo generate, or on the generated GitHub Pages site repository.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

APP_MARKER = 'id="aa-root"'
LINK = '<li><a class="site-page child" href="/algo/"><i class="fa-fw fas fa-book-open"></i><span> 算法档案</span></a></li>'
LINK_HOOK = '<li><a class="site-page child" href="/Tt_link/">'
APP_HTML = '''
<section id="aa-root" class="aa-archive" aria-label="算法档案">
  <header class="aa-heading"><div><p class="aa-kicker"><i class="fas fa-code"></i> ALGOARCHIVE · PUBLIC WORKSPACE</p><h1>算法档案</h1><p class="aa-subtitle">题目、比赛、算法模板，和每一步训练的记录。<span id="aa-sync">等待数据加载</span></p></div><div class="aa-heading-actions"><a class="aa-btn aa-primary" href="/categories/totorial/"><i class="fas fa-book"></i> 博客题解</a><a class="aa-btn" href="/Template/"><i class="fas fa-code"></i> 我的模板</a></div></header>
  <nav class="aa-workspaces" aria-label="算法档案工作区">
   <button type="button" data-aa-view="home" class="active"><i class="fas fa-home"></i> 首页</button>
   <button type="button" data-aa-view="problems" data-aa-oj="codeforces">CF</button>
   <button type="button" data-aa-view="problems" data-aa-oj="atcoder">AtCoder</button>
   <button type="button" data-aa-view="problems" data-aa-oj="luogu">洛谷</button>
   <button type="button" data-aa-view="problems" data-aa-oj="nowcoder">牛客</button>
   <button type="button" data-aa-view="platforms"><i class="fas fa-th-large"></i> 更多 OJ</button>
   <button type="button" data-aa-view="contests"><i class="fas fa-trophy"></i> 完整比赛</button>
   <button type="button" data-aa-view="problems" data-aa-oj="all"><i class="fas fa-list"></i> 全部题目</button>
   <button type="button" data-aa-view="algorithms"><i class="fas fa-layer-group"></i> 算法模板</button>
  </nav>
  <div id="aa-notice" class="aa-notice" hidden></div>
  <div id="aa-content" aria-live="polite"><div class="aa-empty">正在读取算法档案…</div></div>
  <footer class="aa-foot">采用 AlgoArchive 的比赛 / 题目 / 算法模板组织方式；本页为公开只读视图。<a href="https://github.com/Aqiw-source/AlgoArchive" target="_blank" rel="noopener noreferrer">原项目 ↗</a></footer>
</section>
'''


def insert_nav(source: str) -> str:
    if 'href="/algo/"' in source or LINK_HOOK not in source:
        return source
    return source.replace(LINK_HOOK, LINK + LINK_HOOK)


def patch_template(source: str) -> str:
    marker = '<div class="container" id="article-container"></div>'
    if marker not in source:
        raise ValueError('找不到 Butterfly #article-container 容器；请选用已生成的 /Template/index.html')
    html = source.replace(marker, '<div class="container" id="article-container">' + APP_HTML + '</div>', 1)
    html = re.sub(r'<title>[^<]*</title>', '<title>算法档案 | lost.in</title>', html, count=1)
    html = re.sub(r'(<h1\b[^>]*\bid="site-title"[^>]*>).*?(</h1>)', r'\g<1>算法档案\2', html, count=1)
    html = html.replace('https://00lostin00.github.io/Template/index.html', 'https://00lostin00.github.io/algo/index.html')
    html = re.sub(r'(<meta property="og:title" content=")[^"]*', r'\g<1>算法档案', html, count=1)
    html = re.sub(r'(<meta property="og:url" content=")[^"]*', r'\g<1>https://00lostin00.github.io/algo/', html, count=1)
    html = html.replace('</head>', '<link rel="stylesheet" href="/algo/archive.css?v=3"></head>', 1)
    html = html.replace('</body>', '<script defer src="/algo/archive.js?v=3"></script></body>', 1)
    html = html.replace("title: 'Template'", "title: '算法档案'")
    return insert_nav(html)


def build(root: Path, all_pages: bool = False) -> tuple[int, int]:
    root = root.resolve()
    template = root / 'Template' / 'index.html'
    if not template.is_file():
        raise FileNotFoundError(f'必须在已生成的 Butterfly 网站根目录运行；缺少 {template}')
    archive = root / 'algo' / 'index.html'
    archive.parent.mkdir(parents=True, exist_ok=True)
    # Native source/algo/index.md is rendered by Butterfly itself. Never overwrite it.
    if archive.is_file() and APP_MARKER in archive.read_text(encoding='utf-8'):
        return (0, 0)
    archive.write_text(patch_template(template.read_text(encoding='utf-8')), encoding='utf-8')
    count = 0
    if all_pages:
        for page in root.rglob('*.html'):
            if page == archive or any(part.startswith('.') for part in page.relative_to(root).parts):
                continue
            current = page.read_text(encoding='utf-8')
            patched = insert_nav(current)
            if patched != current:
                page.write_text(patched, encoding='utf-8')
                count += 1
    return (1, count)


def main() -> int:
    parser = argparse.ArgumentParser(description='在现有 Butterfly 布局中原生生成 AlgoArchive 只读页面')
    parser.add_argument('site_root', nargs='?', type=Path, default=Path('.'))
    parser.add_argument('--all-pages', action='store_true', help='将算法档案入口加入其他所有 Butterfly 页面导航')
    args = parser.parse_args()
    created, changed = build(args.site_root, args.all_pages)
    print(f'已生成 /algo/index.html（采用网站原生 Butterfly 页面）；额外添加导航的页面数：{changed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
