"""Repack the Truck ETC project without duplicate environments and temporary caches.

Run from any directory: python scripts/package_project.py --output ../truck-etc-app-latest.zip
No third-party libraries required. Maintains a SHA-256 file manifest inside the ZIP.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import zipfile
from pathlib import Path

SKIP_DIRS = {'.venv', '.venv-1', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.swp', '.swo'}
MANIFEST = 'docs/project_tracking/PACKAGE_MANIFEST.csv'
# v13: user-entered environmental readings are site data, never shipped in a project package.
SKIP_FILES = {'data/environment.db', 'data/environment.db-journal'}


def build_archive(project: Path, output: Path) -> int:
    project = project.resolve()
    output = output.resolve()
    files = []
    for path in project.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(project)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix in SKIP_SUFFIXES or str(rel).replace('\\', '/') in ({MANIFEST} | SKIP_FILES):
            continue
        if path.resolve() == output:
            continue
        files.append((path, rel.as_posix()))
    files.sort(key=lambda item: item[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = io.StringIO(newline='')
    writer = csv.writer(manifest)
    writer.writerow(['path', 'size_bytes', 'sha256'])
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for path, rel in files:
            data = path.read_bytes()
            writer.writerow([rel, len(data), hashlib.sha256(data).hexdigest()])
            z.writestr(project.name + '/' + rel, data)
        z.writestr(project.name + '/' + MANIFEST, manifest.getvalue())
    with zipfile.ZipFile(output) as z:
        corrupt = z.testzip()
        if corrupt:
            raise RuntimeError(f'ZIP integrity failure: {corrupt}')
    return len(files) + 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('truck-etc-app-latest.zip'))
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    print(f'Created {args.output.resolve()} with {build_archive(repo, args.output)} files')
