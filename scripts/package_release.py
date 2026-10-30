#!/usr/bin/env python3
"""Package the reviewable OpenFrame source, excluding local data and credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "README.md", "LICENSE", "pyproject.toml", "uv.lock", ".python-version",
    ".env.example", ".gitignore", ".dockerignore", "Dockerfile", "docker-compose.yml", "compose.yaml",
    "frontend/package.json", "frontend/package-lock.json", "frontend/index.html", "frontend/README.md",
    "frontend/tsconfig.json", "frontend/tsconfig.node.json", "frontend/vite.config.ts",
    "frontend/eslint.config.js", "frontend/.prettierrc.json",
    "frontend/src/vendor/sphere-light/LICENSE", "frontend/src/vendor/sphere-light/THREE-LICENSE",
}
SOURCE_DIRS = ("backend", "engine", "custom_nodes", "workflows", "scripts", "docs", "recipes", "tests", "frontend/src")
SOURCE_SUFFIXES = {".py", ".md", ".json", ".toml", ".txt", ".yaml", ".yml", ".sh", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".html", ".svg"}
PUBLIC_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm", ".json", ".txt"}
EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".openframe", "artifacts", "data", "uploads", "renders", "dist", "build", "reference-media"}
EXCLUDED_FILES = {"docs/PRIVATE-DEVELOPMENT.md", "engine/tests/test_runner_modal.py", "tests/test_modal_transfer.py", "engine/tests/validate_sam2.py"}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024


def allowed_name(path: Path) -> bool:
    return not path.is_symlink() and not path.name.startswith(".env") and path.suffix.lower() not in {".pem", ".key", ".sqlite", ".sqlite3", ".db"}


def source_files(root: Path) -> list[Path]:
    chosen = set()
    for relative in ROOT_FILES:
        path = root / relative
        if path.is_file() and not path.is_symlink():
            chosen.add(path)
    for directory in (*SOURCE_DIRS, "frontend/public"):
        base = root / directory
        if not base.is_dir() or base.is_symlink():
            continue
        suffixes = PUBLIC_SUFFIXES if directory == "frontend/public" else SOURCE_SUFFIXES
        for current, directories, filenames in os.walk(base, followlinks=False):
            directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS and not (Path(current) / name).is_symlink())
            for filename in filenames:
                path = Path(current) / filename
                if path.suffix.lower() in suffixes and allowed_name(path) and path.relative_to(root).as_posix() not in EXCLUDED_FILES:
                    chosen.add(path)
    return sorted(chosen, key=lambda path: path.relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "artifacts/release/openframe-source.zip")
    args = parser.parse_args()
    files = source_files(PROJECT_ROOT)
    manifest = []
    total = 0
    for path in files:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(f"Source package refused oversized file: {path.relative_to(PROJECT_ROOT)} ({size} bytes)")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Selected source exceeds 250 MiB; inspect public assets before packaging")
        manifest.append({"path": path.relative_to(PROJECT_ROOT).as_posix(), "bytes": size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    output = args.output.resolve()
    if output in files:
        raise ValueError("Output must not overwrite a source file")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < total + 10 * 1024 * 1024:
        raise ValueError("Not enough free space to package the selected source")
    release = {"project": "OpenFrame", "format": "source-package-v1", "uncompressed_bytes": total, "files": manifest,
               "excludes": ["credentials", "local studio data", "model weights", "dependencies", "reference screenshots", "validation media", "private GPU worker/setup/tests"]}
    # An unchanged source tree should not rewrite an identical release archive.
    if output.is_file():
        try:
            with zipfile.ZipFile(output) as previous:
                if json.loads(previous.read("openframe/RELEASE-MANIFEST.json")) == release:
                    print(json.dumps({"archive": str(output), "files": len(files), "unchanged": True}))
                    return 0
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
            pass
    temporary = output.with_name(output.name + ".partial")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path, entry in zip(files, manifest):
                info = zipfile.ZipInfo("openframe/" + entry["path"], date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o644 << 16)
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Source changed during packaging: {entry['path']}. Retry after edits finish.")
                archive.writestr(info, content)
            info = zipfile.ZipInfo("openframe/RELEASE-MANIFEST.json", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, json.dumps(release, indent=2) + "\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"archive": str(output), "files": len(files), "uncompressed_bytes": total,
                      "archive_bytes": output.stat().st_size, "unchanged": False}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
