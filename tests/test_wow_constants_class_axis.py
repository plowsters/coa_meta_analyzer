import pytest

from coa_client_extract.wow_constants import build_class_axis, class_roster

REF = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
POWER = {"map": {"0": "mana", "1": "rage", "3": "energy"}}


def _rows(pairs):  # (id, power_type)
    return [{"id": i, "power_type": p, "name": f"C{i}"} for i, p in pairs]


def test_exact_and_default_power_map():
    axis = build_class_axis(_rows([(i, 0) for i in REF]), reference_expected_ids=REF,
                            reference_holes=[10], power_type_enum=POWER)
    assert axis["comparison"] == "exact" and class_roster(axis) == REF
    assert axis["default_power_type_by_wow_class_id"]["1"] == "mana"


def test_extended_when_superset():
    axis = build_class_axis(_rows([(i, 0) for i in REF] + [(12, 3)]), reference_expected_ids=REF,
                            reference_holes=[10], power_type_enum=POWER)
    assert axis["comparison"] == "extended"
    assert axis["default_power_type_by_wow_class_id"]["12"] == "energy"


def test_changed_when_reference_id_missing():
    axis = build_class_axis(_rows([(1, 0), (2, 1)]), reference_expected_ids=REF,
                            reference_holes=[10], power_type_enum=POWER)
    assert axis["comparison"] == "changed"


def test_duplicate_and_unmapped_power_raise():
    with pytest.raises(ValueError):
        build_class_axis(_rows([(1, 0), (1, 0)]), reference_expected_ids=REF,
                         reference_holes=[10], power_type_enum=POWER)
    with pytest.raises(ValueError):
        build_class_axis(_rows([(1, 99)]), reference_expected_ids=[1], reference_holes=[],
                         power_type_enum=POWER)
