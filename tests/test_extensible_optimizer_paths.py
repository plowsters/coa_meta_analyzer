from __future__ import annotations

from pathlib import Path

from coa_optimizer_extensible import resolve_entries_path


def test_resolve_entries_path_uses_scraper_dist_fallback(tmp_path: Path):
    requested = Path("dist/coa_entries.jsonl")
    fallback = tmp_path / "coa_scraper" / "dist" / "coa_entries.jsonl"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("{}", encoding="utf-8")

    resolved, note = resolve_entries_path(requested, cwd=tmp_path)

    assert resolved == fallback
    assert note is not None
    assert "coa_scraper/dist/coa_entries.jsonl" in note


def test_resolve_entries_path_keeps_existing_requested_path(tmp_path: Path):
    requested = tmp_path / "dist" / "coa_entries.jsonl"
    requested.parent.mkdir(parents=True)
    requested.write_text("{}", encoding="utf-8")

    resolved, note = resolve_entries_path(requested, cwd=tmp_path)

    assert resolved == requested
    assert note is None


def test_resolve_entries_path_keeps_missing_nonstandard_path(tmp_path: Path):
    requested = Path("custom/entries.jsonl")

    resolved, note = resolve_entries_path(requested, cwd=tmp_path)

    assert resolved == requested
    assert note is None
