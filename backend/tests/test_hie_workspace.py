from pathlib import Path

import pytest

from app.services.hie_workspace import (
    HIEFixtureError,
    create_disposable_workspace,
)


def test_creates_disposable_copy_and_preserves_source(tmp_path):
    source = tmp_path / "fixture"
    source.mkdir()
    (source / "brief.md").write_text("# Original\n", encoding="utf-8")
    nested = source / "data"
    nested.mkdir()
    (nested / "sample.json").write_text('{"ok": true}', encoding="utf-8")

    with create_disposable_workspace(source) as disposable:
        assert disposable.file_count == 2
        assert (disposable.root / "brief.md").read_text(encoding="utf-8") == "# Original\n"
        assert (disposable.root / "data" / "sample.json").exists()
        (disposable.root / "brief.md").write_text("# Changed in probe\n", encoding="utf-8")
        assert (source / "brief.md").read_text(encoding="utf-8") == "# Original\n"
        root = disposable.root

    assert not root.exists()


def test_rejects_symlink_files_and_directories(tmp_path):
    source = tmp_path / "fixture"
    source.mkdir()
    external = tmp_path / "external.md"
    external.write_text("do not copy", encoding="utf-8")
    (source / "escape.md").symlink_to(external)
    with pytest.raises(HIEFixtureError, match="Symlinks"):
        create_disposable_workspace(source)


def test_rejects_code_like_or_unallowlisted_files(tmp_path):
    source = tmp_path / "fixture"
    source.mkdir()
    (source / "run.py").write_text("print('not executed')", encoding="utf-8")
    with pytest.raises(HIEFixtureError, match="not allowlisted"):
        create_disposable_workspace(source)


def test_rejects_single_file_and_total_size_limits(tmp_path):
    source = tmp_path / "fixture"
    source.mkdir()
    (source / "large.md").write_text("x" * 12, encoding="utf-8")
    with pytest.raises(HIEFixtureError, match="per-file"):
        create_disposable_workspace(source, max_single_file_bytes=10)


def test_rejects_invalid_limits_and_non_directory_source(tmp_path):
    source = tmp_path / "fixture"
    source.mkdir()
    with pytest.raises(HIEFixtureError, match="positive integers"):
        create_disposable_workspace(source, max_files=0)
    file_path = tmp_path / "not-dir.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(HIEFixtureError, match="directory"):
        create_disposable_workspace(file_path)
