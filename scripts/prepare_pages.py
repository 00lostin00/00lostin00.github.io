"""Stage the generated site, excluding repository maintenance files."""
from pathlib import Path
import argparse
import shutil

EXCLUDE = {'scripts', 'tools', 'tests', 'config', 'data', 'node_modules', 'source',
           'themes', 'scaffolds', 'public', 'db.json', 'package.json',
           'package-lock.json', 'git.txt', 'ALGOARCHIVE.md'}


def stage(root: Path, destination: Path) -> int:
    root, destination = root.resolve(), destination.resolve()
    if destination == root or not destination.is_relative_to(root):
        raise ValueError('Destination must be a separate directory inside the generated site')
    if not (root / 'index.html').is_file() or not (root / 'algo/index.html').is_file():
        raise ValueError('Expected a generated Hexo site with index.html and algo/index.html')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Destination must be empty')
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in root.iterdir():
        if item == destination or item.name.startswith('.') or item.name in EXCLUDE:
            continue
        if item.suffix.lower() in {'.zip', '.sqlite', '.sqlite3', '.db', '.py', '.yml'}:
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(f'Staged {stage(args.root, args.destination)} site entries')
