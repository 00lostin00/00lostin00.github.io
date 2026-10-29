import importlib.util
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / 'tools/algo' if (BASE / 'tools/algo').is_dir() else BASE / 'scripts'
spec = importlib.util.spec_from_file_location('prepare_pages', SCRIPTS / 'prepare_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


class PagesTests(unittest.TestCase):
    def test_staging_keeps_site_and_excludes_maintenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ['index.html', 'algo/index.html', 'algo/data.json',
                         'css/index.css', 'scripts/sync_oj.py', 'config/oj_sources.json',
                         '.github/workflows/deploy.yml', '.oj-cache/data.json']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('test', encoding='utf8')
            destination = root / '.pages'
            pages.stage(root, destination)
            for name in ['index.html', 'algo/index.html', 'algo/data.json', 'css/index.css']:
                self.assertTrue((destination / name).exists())
            for name in ['scripts', 'config', '.github', '.oj-cache']:
                self.assertFalse((destination / name).exists())

    def test_staging_requires_generated_site_and_empty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                pages.stage(root, root / '.pages')
            with self.assertRaises(ValueError):
                pages.stage(root, root)


if __name__ == '__main__':
    unittest.main()
