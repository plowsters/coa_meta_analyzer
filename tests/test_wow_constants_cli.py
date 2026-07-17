import json
import struct
from pathlib import Path

import pytest

from coa_client_extract.archive_backend import FakeArchiveBackend
from coa_client_extract.cli import main, wow_constants_command
from coa_client_extract.errors import BackendUnavailable


def _client(tmp_path: Path) -> Path:
    data = tmp_path / "Data"
    data.mkdir()
    for name in ("common.MPQ", "patch.MPQ", "patch-M.MPQ"):
        (data / name).write_bytes(b"MPQ\x1a")
    return data


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def _chr_classes(pairs):
    strings = b"\x00" + b"".join(f"C{i}".encode() + b"\x00" for i, _ in pairs)
    rows, off = [], 1
    for i, p in pairs:
        cells = [0] * 60
        cells[0], cells[2], cells[5] = i, p, off
        off += len(f"C{i}") + 1
        rows.append(struct.pack("<" + "I" * 60, *cells))
    return struct.pack("<4sIIII", b"WDBC", len(pairs), 60, 240, len(strings)) + b"".join(rows) + strings


def make_backend(**overrides):
    ids = [(i, 0) for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]]
    e = {
        "DBFilesClient\\gtCombatRatings.dbc": [(Path("patch-M.MPQ"), _implicit([float(i) for i in range(3200)]))],
        "DBFilesClient\\gtOCTClassCombatRatingScalar.dbc": [(Path("patch-M.MPQ"), _implicit([1.0] * (12 * 32)))],
        "DBFilesClient\\gtChanceToMeleeCrit.dbc": [(Path("patch-M.MPQ"), _implicit([0.05] * (12 * 100)))],
        "DBFilesClient\\gtChanceToMeleeCritBase.dbc": [(Path("patch-M.MPQ"), _implicit([0.01] * 12))],
        "DBFilesClient\\gtChanceToSpellCrit.dbc": [(Path("patch-M.MPQ"), _implicit([0.05] * (12 * 100)))],
        "DBFilesClient\\gtChanceToSpellCritBase.dbc": [(Path("patch-M.MPQ"), _implicit([0.01] * 12))],
        "DBFilesClient\\gtRegenMPPerSpt.dbc": [(Path("patch-M.MPQ"), _implicit([0.1] * (12 * 100)))],
        "DBFilesClient\\ChrClasses.dbc": [(Path("patch-M.MPQ"), _chr_classes(ids))],
    }
    for k, v in overrides.items():
        key = "DBFilesClient\\" + k + ".dbc"
        if v is None:
            e.pop(key, None)
        else:
            e[key] = [(Path("patch-M.MPQ"), v)]
    return FakeArchiveBackend(e)


def _plan(client_root):
    from coa_client_extract.archive_plan import discover_plan
    return discover_plan(client_root)


def test_recon_only_writes_report_not_snapshot(tmp_path):
    out = tmp_path / "out"
    report = wow_constants_command(_client(tmp_path), out, backend=make_backend(), recon_only=True)
    assert report["class_axis"]["comparison"] == "exact"
    assert (out / "coa_wow_constants_recon.json").is_file()
    assert not (out / "coa_wow_constants.json").exists()


def test_cli_recon_only_fails_closed_without_stormlib(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise BackendUnavailable("StormLib not found")
    monkeypatch.setattr("coa_client_extract.stormlib_backend.StormLibBackend", boom, raising=False)
    rc = main(["wow-constants", "--client-root", str(_client(tmp_path)),
               "--out", str(tmp_path / "o"), "--recon-only"])
    assert rc == 2
