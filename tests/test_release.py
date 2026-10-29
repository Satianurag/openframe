"""Bounded release-package checks using temporary fixture sources, not user data."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import package_release


class SourceReleaseTests(unittest.TestCase):
    def test_allowlist_excludes_private_runtime_data_and_symlinks(self):
        with tempfile.TemporaryDirectory(prefix="openframe-package-test-") as folder:
            root = Path(folder)
            files = {
                "README.md": "Public readme",
                ".env.example": "OPENFRAME_DATA_DIR=.openframe",
                ".env": "API_KEY=PRIVATE_FIXTURE",
                "backend/app.py": "# source",
                "backend/.env.local": "PRIVATE_FIXTURE",
                "backend/session.key": "PRIVATE_FIXTURE",
                "backend/__pycache__/hidden.py": "PRIVATE_FIXTURE",
                "backend/data/user.json": "PRIVATE_FIXTURE",
                "artifacts/reference/image.png": "PRIVATE_FIXTURE",
                ".openframe/settings.json": "PRIVATE_FIXTURE",
                "recipes/example.json": "{}",
                "frontend/public/fonts/OFL.txt": "public license",
                "frontend/public/fonts/SpaceGrotesk.ttf": "public font fixture",
                "frontend/src/main.tsx": "// source",
                "frontend/node_modules/private/index.js": "PRIVATE_FIXTURE",
            }
            for name, text in files.items():
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(text)
            (root / "backend/linked.py").symlink_to(root / ".env")
            (root / "backend/linked_directory").symlink_to(root / ".openframe", target_is_directory=True)
            selected = {path.relative_to(root).as_posix() for path in package_release.source_files(root)}
            self.assertEqual(selected, {"README.md", ".env.example", "backend/app.py", "recipes/example.json", "frontend/public/fonts/OFL.txt", "frontend/public/fonts/SpaceGrotesk.ttf", "frontend/src/main.tsx"})

    def test_archive_roundtrip_hashes_and_unchanged_archive_reuse(self):
        with tempfile.TemporaryDirectory(prefix="openframe-package-test-") as folder:
            root = Path(folder)
            content = b"# Reproducible fixture source\n"
            (root / "README.md").write_bytes(content)
            (root / ".env").write_text("SECRET_FIXTURE_DO_NOT_EXPORT")
            archive = root / "release.zip"
            stdout = io.StringIO()
            with patch.object(package_release, "PROJECT_ROOT", root), patch("sys.argv", ["package_release.py", "--output", str(archive)]), contextlib.redirect_stdout(stdout):
                self.assertEqual(package_release.main(), 0)
                first_mtime = archive.stat().st_mtime_ns
                first_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertEqual(package_release.main(), 0)
            self.assertEqual(first_mtime, archive.stat().st_mtime_ns)
            self.assertEqual(first_hash, hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as opened:
                self.assertIsNone(opened.testzip())
                self.assertEqual(set(opened.namelist()), {"openframe/README.md", "openframe/RELEASE-MANIFEST.json"})
                self.assertEqual(opened.read("openframe/README.md"), content)
                manifest = json.loads(opened.read("openframe/RELEASE-MANIFEST.json"))
                self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(content).hexdigest())
            self.assertTrue(json.loads(stdout.getvalue().splitlines()[-1])["unchanged"])
            self.assertFalse(archive.with_name("release.zip.partial").exists())


if __name__ == "__main__":
    unittest.main()
