import struct
from pathlib import Path

import pytest

pytestmark = pytest.mark.stormlib

from coa_client_extract.stormlib_backend import StormLibBackend  # noqa: E402


def _dbc(value: int) -> bytes:
    row = struct.pack("<II", 1, value)
    return struct.pack("<4sIIII", b"WDBC", 1, 2, 8, 1) + row + b"\x00"


def _value_of(data: bytes) -> int:
    # header(20) + id(4) -> value cell
    (value,) = struct.unpack_from("<I", data, 24)
    return value


def test_patch_overrides_base(tmp_path):
    from tests.helpers.build_mpq import build_mpq

    base = build_mpq(tmp_path / "common.MPQ", {"DBFilesClient\\Test.dbc": _dbc(100)})
    patch = build_mpq(tmp_path / "patch-C.MPQ", {"DBFilesClient\\Test.dbc": _dbc(999)})

    backend = StormLibBackend()
    member = backend.read_effective_file(base, (patch,), "DBFilesClient\\Test.dbc")

    # The patched value (999) must win over the base value (100).
    assert _value_of(member.data) == 999
    # Provenance comes from StormLib's own patch-chain report, not the attach order.
    # For a complete override the winning archive is the sole supplier, and it is the
    # effective archive.
    assert member.effective_archive == patch
    assert patch in member.patch_chain
    assert member.patch_chain[-1] == patch


def test_base_only_file_reports_base_as_effective(tmp_path):
    from tests.helpers.build_mpq import build_mpq

    # The base supplies Test.dbc; the patch is a valid archive that does not override it.
    base = build_mpq(tmp_path / "common.MPQ", {"DBFilesClient\\Test.dbc": _dbc(100)})
    patch = build_mpq(tmp_path / "patch-C.MPQ", {"DBFilesClient\\Other.dbc": _dbc(7)})

    backend = StormLibBackend()
    member = backend.read_effective_file(base, (patch,), "DBFilesClient\\Test.dbc")

    # No patch supplies the file, so the base bytes win and the base is the effective archive.
    assert _value_of(member.data) == 100
    assert member.effective_archive == base
    assert member.patch_chain[-1] == base
