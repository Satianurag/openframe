"""Regression for ONNX Runtime's external-data directory security boundary."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from engine.models import _materialize_sibling_file

class OnnxExternalData(TestCase):
    def test_cached_symlink_becomes_a_colocated_file_without_changing_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cache=root/'cache';cache.mkdir();models=root/'models';models.mkdir()
            source=cache/'hash';source.write_bytes(b'cached-checkpoint')
            target=models/'external.bin';target.symlink_to(source)
            _materialize_sibling_file(target)
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.resolve().parent,models.resolve())
            self.assertEqual(target.read_bytes(),source.read_bytes())
            self.assertTrue(target.samefile(source))
            _materialize_sibling_file(target)
            self.assertTrue(target.samefile(source))

    def test_volumes_without_hardlinks_copy_once_and_preserve_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'cached';source.write_bytes(b'checkpoint')
            target=root/'model';target.symlink_to(source)
            with patch('os.link',side_effect=OSError('hardlinks unavailable')):
                _materialize_sibling_file(target)
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_bytes(),source.read_bytes())
            self.assertFalse(target.samefile(source))
            self.assertEqual(list(root.glob('*.partial')),[])
