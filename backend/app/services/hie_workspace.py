"""Safe, disposable filesystem fixtures for HIE experiments.

This module deliberately copies data only. It never executes project code, follows
symlinks, writes into the source workspace, or provides a production adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable


MAX_FIXTURE_FILES = 500
MAX_FIXTURE_BYTES = 5 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 1024 * 1024


class HIEFixtureError(ValueError):
    """The source fixture cannot be copied within the isolation contract."""


@dataclass
class DisposableWorkspace:
    """Context-managed, writable copy of a small data-only fixture."""

    source: Path
    _temp: tempfile.TemporaryDirectory[str]
    root: Path
    file_count: int
    total_bytes: int

    def __enter__(self) -> "DisposableWorkspace":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        self._temp.cleanup()


def create_disposable_workspace(
    source: str | os.PathLike[str],
    *,
    allowed_suffixes: Iterable[str] = (".md", ".txt", ".json", ".yaml", ".yml"),
    max_files: int = MAX_FIXTURE_FILES,
    max_total_bytes: int = MAX_FIXTURE_BYTES,
    max_single_file_bytes: int = MAX_SINGLE_FILE_BYTES,
) -> DisposableWorkspace:
    """Create a disposable copy of a fixture containing allowlisted data files.

    The source is read-only from this function's perspective. Symlinks, special
    files, executable/code-like suffixes, and paths resolving outside the source
    are rejected. The returned workspace must be used as a context manager.
    """
    src = Path(source).expanduser()
    if not src.exists() or not src.is_dir() or src.is_symlink():
        raise HIEFixtureError("Fixture source must be an existing, non-symlink directory")
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in
           (max_files, max_total_bytes, max_single_file_bytes)):
        raise HIEFixtureError("Fixture limits must be positive integers")

    raw_suffixes = tuple(allowed_suffixes)
    if not raw_suffixes or any(
        not isinstance(s, str) or not s.startswith(".") or len(s) < 2
        for s in raw_suffixes
    ):
        raise HIEFixtureError("Allowed suffixes must be a non-empty set of extensions")
    suffixes = {s.lower() for s in raw_suffixes}

    src = src.resolve(strict=True)
    entries: list[tuple[Path, Path, int]] = []
    total = 0

    for current, dirs, filenames in os.walk(src, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for dirname in sorted(dirs):
            p = current_path / dirname
            if p.is_symlink():
                raise HIEFixtureError("Symlinks are not permitted in fixtures")
            if not p.is_dir():
                raise HIEFixtureError("Fixture contains a non-directory entry")
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_symlink() or not path.is_file():
                raise HIEFixtureError("Symlinks and special files are not permitted")
            try:
                relative = path.relative_to(src)
                resolved = path.resolve(strict=True)
                resolved.relative_to(src)
            except (ValueError, OSError) as exc:
                raise HIEFixtureError("Fixture path escapes its source directory") from exc
            if path.suffix.lower() not in suffixes:
                raise HIEFixtureError(f"Fixture file type is not allowlisted: {path.suffix or '<none>'}")
            size = path.stat().st_size
            if size > max_single_file_bytes:
                raise HIEFixtureError("Fixture file exceeds per-file size limit")
            total += size
            entries.append((path, relative, size))
            if len(entries) > max_files:
                raise HIEFixtureError("Fixture contains too many files")
            if total > max_total_bytes:
                raise HIEFixtureError("Fixture exceeds total size limit")

    temp = tempfile.TemporaryDirectory(prefix="mosaic-hie-")
    root = Path(temp.name) / "workspace"
    try:
        root.mkdir(mode=0o700)
        for original, relative, _ in entries:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Open destination exclusively; copy bytes only, never metadata/permissions.
            with original.open("rb") as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=64 * 1024)
            destination.chmod(0o600)
        return DisposableWorkspace(
            source=src,
            _temp=temp,
            root=root,
            file_count=len(entries),
            total_bytes=total,
        )
    except Exception:
        temp.cleanup()
        raise
