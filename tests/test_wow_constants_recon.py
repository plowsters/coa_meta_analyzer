import struct
from pathlib import Path

from coa_client_extract.archive_backend import FakeArchiveBackend
from coa_client_extract.wow_constants import recon, load_authored_input, load_axis_policy


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def _chr_classes(pairs):  # (id, power_type)
    strings = b"\x00" + b"".join(f"C{i}".encode() + b"\x00" for i, _ in pairs)
    rows, off = [], 1
    for i, p in pairs:
        cells = [0] * 60
        cells[0], cells[2], cells[5] = i, p, off      # id@0, power@2, name@5
        off += len(f"C{i}") + 1
        rows.append(struct.pack("<" + "I" * 60, *cells))
    return struct.pack("<4sIIII", b"WDBC", len(pairs), 60, 240, len(strings)) + b"".join(rows) + strings


def _backend():
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
    return FakeArchiveBackend(e), Path("common.MPQ"), (Path("patch-M.MPQ"),)


def _inputs():
    axis = load_authored_input("gt_axis_policy")
    layouts, ls, rs = load_axis_policy(axis.payload)
    return ((layouts, ls, rs), load_authored_input("rating_enum").payload,
            load_authored_input("power_type_enum").payload, axis.payload["class_axis"])


def test_recon_reports_findings_class_axis_and_context():
    backend, root, attach = _backend()
    axis_policy, rating_enum, power_enum, ref_axis = _inputs()
    r = recon(backend, root, attach, axis_policy=axis_policy, rating_enum=rating_enum,
              power_type_enum=power_enum, reference_class_axis=ref_axis)
    cr = r["tables"]["combat_ratings"]
    assert cr["available"] and cr["source_records"] == 3200 and cr["drift"] is False
    assert cr["physical_form"] == "implicit_row" and cr["finite_ok"] is True
    assert cr["coverage"]["emitted_entries"] == 2500
    assert r["class_axis"]["comparison"] == "exact"
    assert r["enum_coverage"]["unmapped_rating_ids"] == []
    assert r["class_context_resolution"] == "unproven"
    assert r["tables"]["oct_regen_mp"]["available"] is False
