from pathlib import Path

import pytest

from coa_client_extract.archive_backend import FakeArchiveBackend
from coa_client_extract.archive_plan import (
    ArchivePlan, discover_plan, family_of, validate_ordering,
)
from coa_client_extract.errors import ArchiveError

FAMILY = [
    "common.MPQ", "common-2.MPQ", "expansion.MPQ", "lichking.MPQ",
    "patch.MPQ", "patch-2.MPQ", "patch-3.MPQ",
    "patch-A.MPQ", "patch-T.MPQ",
    "patch-C.MPQ", "patch-CA.MPQ", "patch-CHA.MPQ", "patch-CZZ.MPQ",
    "patch-WA.MPQ", "patch-WB1.MPQ", "patch-WC3.MPQ",  # digit-suffixed Reborn
]


def _make_client(tmp_path: Path) -> Path:
    data = tmp_path / "Data"
    data.mkdir()
    for name in FAMILY:
        (data / name).write_bytes(b"MPQ\x1a")
    area = data / "area-52"
    area.mkdir()
    (area / "patch-D.MPQ").write_bytes(b"MPQ\x1a")
    return data


def test_discover_plan_partitions_families(tmp_path):
    plan = discover_plan(_make_client(tmp_path))
    names = {p.name for p in plan.patch_archives}
    assert "patch-C.MPQ" in names and "patch-CZZ.MPQ" in names
    assert "patch-T.MPQ" in names  # T-family is an included "other" patch (supplies real Spell.dbc)
    assert "patch-WA.MPQ" not in names  # Reborn excluded
    # digit-suffixed Reborn archives must also be excluded, not swept into the CoA chain
    assert "patch-WB1.MPQ" not in names and "patch-WC3.MPQ" not in names
    reborn_names = {p.name for p in plan.excluded["reborn"]}
    assert {"patch-WA.MPQ", "patch-WB1.MPQ", "patch-WC3.MPQ"} <= reborn_names
    assert all("patch-D.MPQ" != p.name for p in plan.patch_archives)  # Area-52 excluded
    assert {p.name for p in plan.base_archives} == {
        "common.MPQ", "common-2.MPQ", "expansion.MPQ", "lichking.MPQ"
    }
    assert "reborn" in plan.excluded and "area52" in plan.excluded


def test_family_of_classifies_raw_signal():
    assert family_of("patch-CA.MPQ") == "coa"
    assert family_of("patch-CHA.MPQ") == "coa"
    assert family_of("patch-WB1.MPQ") == "reborn"  # digit-suffixed Reborn
    assert family_of("common.MPQ") == "base"
    assert family_of("patch-T.MPQ") == "other"  # undecided until M1.14B


def test_patch_c_family_orders_after_numeric_patches(tmp_path):
    plan = discover_plan(_make_client(tmp_path))
    order = [p.name for p in plan.patch_archives]
    assert order.index("patch.MPQ") < order.index("patch-C.MPQ")
    assert order.index("patch-C.MPQ") < order.index("patch-CA.MPQ")
    assert order.index("patch-CA.MPQ") < order.index("patch-CZZ.MPQ")


def test_plan_to_dict_shape(tmp_path):
    plan = discover_plan(_make_client(tmp_path))
    doc = plan.to_dict()
    assert doc["schema_version"] == "coa-client-archive-plan-v1"
    assert doc["ordering_rule"] == "coa-archive-order-v1"
    assert isinstance(doc["patch_archives"], list)


def test_validate_ordering_detects_wrong_effective(tmp_path):
    plan = discover_plan(_make_client(tmp_path))
    backend = FakeArchiveBackend(
        {"DBFilesClient\\Spell.dbc": [(Path("common.MPQ"), b"a"), (Path("patch-CA.MPQ"), b"b")]}
    )
    validate_ordering(plan, backend, "DBFilesClient\\Spell.dbc", Path("patch-CA.MPQ"))
    with pytest.raises(ArchiveError):
        validate_ordering(plan, backend, "DBFilesClient\\Spell.dbc", Path("patch-C.MPQ"))


def test_open_chain_attaches_all_base_and_patch_archives(tmp_path):
    plan = discover_plan(_make_client(tmp_path))
    root, attach = plan.open_chain
    assert root.name == "common.MPQ"
    attach_names = [p.name for p in attach]
    # the three non-root base archives are attached, ahead of the patches
    for name in ("common-2.MPQ", "expansion.MPQ", "lichking.MPQ"):
        assert name in attach_names
        assert attach_names.index(name) < attach_names.index("patch.MPQ")
    assert "patch-WA.MPQ" not in attach_names  # Reborn stays excluded


def test_open_chain_raises_without_base(tmp_path):
    data = tmp_path / "Data"
    data.mkdir()
    (data / "patch-C.MPQ").write_bytes(b"MPQ\x1a")  # patches but no base archives
    plan = discover_plan(data)
    with pytest.raises(ArchiveError):
        _ = plan.open_chain
