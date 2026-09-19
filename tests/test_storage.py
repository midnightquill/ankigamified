import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support
from gamified_under_test.storage import ProgressStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'user_files' / 'progress.json'

    def test_migration_once_and_profile_isolation(self):
        store = ProgressStore(self.path)
        self.assertEqual(store.load_profile('Japanese', {'best_streak': 54}), {'best_streak': 54})
        store.save('Japanese', {'best_streak': 54})
        store = ProgressStore(self.path)
        self.assertEqual(store.load_profile('Spanish', {'best_streak': 54}), {})
        store.save('Spanish', {'best_streak': 7})
        self.assertEqual(store.load_profile('Japanese', {}), {'best_streak': 54})

    def test_atomic_failure_keeps_previous_save_and_cleans_temp(self):
        store = ProgressStore(self.path)
        store.save('test', {'daily_reviews': 3})
        with patch('gamified_under_test.storage.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                store.save('test', {'daily_reviews': 4})
        self.assertEqual(json.loads(self.path.read_text())['profiles']['test']['daily_reviews'], 3)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        store.save('test', {'daily_reviews': 4})
        self.assertEqual(ProgressStore(self.path).load_profile('test', {})['daily_reviews'], 4)

    def test_invalid_file_is_not_overwritten(self):
        self.path.parent.mkdir()
        self.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            ProgressStore(self.path)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_unknown_version_is_not_overwritten(self):
        self.path.parent.mkdir()
        original = '{"version": 99, "profiles": {}}'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            ProgressStore(self.path)
        self.assertEqual(self.path.read_text(), original)


if __name__ == '__main__':
    unittest.main()
