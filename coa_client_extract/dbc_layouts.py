from __future__ import annotations

from .wdbc import DbcLayout, FieldSpec

# Stock WotLK 3.3.5a offsets. Ascension may shift/extend these; drift detection
# flags that, and the Task 10 acceptance test (spell 805775) validates/corrects them.
SPELL_FAMILY: dict[str, DbcLayout] = {
    "Spell": DbcLayout(
        name="Spell",
        expected_field_count=234,
        expected_record_size=234 * 4,
        columns={
            "id": FieldSpec(0, "uint32"),
            "category": FieldSpec(1, "uint32"),
            "school_mask": FieldSpec(139, "uint32"),
            "power_type": FieldSpec(110, "int32"),
            "casting_time_index": FieldSpec(28, "uint32"),
            "duration_index": FieldSpec(24, "uint32"),
            "range_index": FieldSpec(29, "uint32"),
            "spell_icon_id": FieldSpec(133, "uint32"),
            "name": FieldSpec(136, "str"),  # localized name, enUS column
        },
    ),
    "SpellCastTimes": DbcLayout(
        name="SpellCastTimes",
        expected_field_count=4,
        expected_record_size=4 * 4,
        columns={"id": FieldSpec(0, "uint32"), "base_ms": FieldSpec(1, "int32")},
    ),
    "SpellDuration": DbcLayout(
        name="SpellDuration",
        expected_field_count=4,
        expected_record_size=4 * 4,
        columns={"id": FieldSpec(0, "uint32"), "base_ms": FieldSpec(1, "int32")},
    ),
    "SpellRange": DbcLayout(
        name="SpellRange",
        expected_field_count=39,
        expected_record_size=39 * 4,
        columns={
            "id": FieldSpec(0, "uint32"),
            "min_yd": FieldSpec(1, "float"),
            "max_yd": FieldSpec(3, "float"),
        },
    ),
}
