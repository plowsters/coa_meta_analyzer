import struct

import pytest

pytestmark = pytest.mark.stormlib

from coa_client_extract.stormlib_backend import StormLibBackend  # noqa: E402


def _stormlib_available() -> bool:
    try:
        StormLibBackend()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _stormlib_available(), reason="StormLib shared library not installed")
def test_stormlib_backend_reads_a_gametable(tmp_path):
    # Confirm the real StormLib-backed path decodes a GameTable through parse_gametable
    # (mirrors tests/test_client_extract_integration_stormlib.py's build_mpq + read pattern).
    from tests.helpers.build_mpq import build_mpq
    from coa_client_extract.wdbc import parse_gametable

    gt = struct.pack("<4sIIII", b"WDBC", 3, 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in (1.5, 2.5, 3.5))
    base = build_mpq(tmp_path / "common.MPQ", {"DBFilesClient\\gtCombatRatings.dbc": gt})

    member = StormLibBackend().read_effective_file(base, (), "DBFilesClient\\gtCombatRatings.dbc")
    table = parse_gametable(member.data, physical_form="implicit_row",
                            expected_field_count=1, expected_record_size=4)
    assert [r["value"] for r in table.rows] == [1.5, 2.5, 3.5]
