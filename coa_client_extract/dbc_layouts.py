from __future__ import annotations

from dataclasses import dataclass, field

from .wdbc import DbcLayout, FieldSpec

# Stock WotLK 3.3.5a offsets. Ascension may shift/extend these; drift detection
# flags that, and the Task 10 acceptance test (spell 805775) validates/corrects them.
#
# M1.14A scope: this is the deliberately reduced spell family — Spell plus the three
# index tables (cast time, duration, range) that resolve Spell.dbc's *_index columns. The
# umbrella spec's fuller mechanical set (SpellCooldowns/category cooldowns, SpellRuneCost,
# and the SpellEffect `effects[]` join) is deferred to a later M1.14 sub-milestone; those
# tables are load-bearing for the M1.16 power model, not for M1.14A extraction. See
# docs/data/client-spell-schema.md ("Mechanics scope").
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

# --- CoA advancement companion tables (headers + name column verified on the real client 2026-07-13) ---
# Col 0 = row id; col 1 = name string (verified) for the two *Types tables. Essence has no strings.
CHARACTER_ADVANCEMENT_CLASS_TYPES = DbcLayout(
    name="CharacterAdvancementClassTypes", expected_field_count=23, expected_record_size=92,
    columns={"id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str")},
)
CHARACTER_ADVANCEMENT_TAB_TYPES = DbcLayout(
    name="CharacterAdvancementTabTypes", expected_field_count=19, expected_record_size=76,
    columns={"id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str")},
)
CHARACTER_ADVANCEMENT_ESSENCE = DbcLayout(
    name="CharacterAdvancementEssence", expected_field_count=9, expected_record_size=36,
    columns={"id": FieldSpec(0, "uint32")},   # per-level progression, extracted raw (Task 6)
)
# SkillLineAbility: id(0), skill_line(1), spell(2). The CoA skill-line SET is proven empirically at
# extraction time (attribution.derive_coa_skill_lines) from the lines that carry graph CoA spells —
# NOT a hard-coded range, since CoA spells attach to per-spec lines, not only the 475-495 class band.
CHARACTER_ADVANCEMENT_SKILL_LINE_ABILITY = DbcLayout(
    name="SkillLineAbility", expected_field_count=14, expected_record_size=56,
    columns={"id": FieldSpec(0, "uint32"), "skill_line": FieldSpec(1, "uint32"),
             "spell": FieldSpec(2, "uint32")},
)


@dataclass(frozen=True)
class CharacterAdvancementLayout:
    """Resolved column map for CharacterAdvancement.dbc. Only the three anchors are known a
    priori (verified: node id col 0, spell id col 5, class-type FK col 32). Every other field is
    filled by the Task 3 decode harness and semantically validated before use; None / () means
    'not yet resolved to high confidence' and blocks that field from canonical emission."""
    node_id_col: int = 0
    spell_id_col: int = 5
    class_type_col: int = 32
    tab_type_col: int | None = None
    entry_type_col: int | None = None
    name_col: int | None = None
    icon_col: int | None = None
    ae_cost_col: int | None = None
    te_cost_col: int | None = None
    required_level_col: int | None = None
    required_tab_ae_col: int | None = None
    required_tab_te_col: int | None = None
    max_rank_col: int | None = None
    row_col: int | None = None
    column_col: int | None = None
    node_type_col: int | None = None
    connected_node_cols: tuple[int, ...] = ()
    required_id_cols: tuple[int, ...] = ()
    header_field_count: int = 179
    header_record_size: int = 692
    # Proven numeric->string entry-type map from the Task 3 decode (JSON keys are strings, e.g.
    # {"0": "Ability", "1": "Talent"}). read_advancement consumes THIS, never a hard-coded table,
    # so the mapping is load-bearing proof rather than an assumption. Empty until decode fills it.
    entry_type_map: dict = field(default_factory=dict)
    # Per-legality-field proof from the Task 3 decode: field name -> "high" | "medium" | "unproven".
    # read_advancement emits a field into `legality` ONLY when its confidence is "high"; a configured
    # column with no "high" confidence is treated as unproven and withheld (never assumed).
    confidence: dict = field(default_factory=dict)


# Anchors-only default; Task 3's client-tier decode overwrites this with the resolved columns and
# their proven confidence. The anchors themselves (node_id/spell_id/class_type) are structurally
# verified, but legality fields stay unproven until decode fills `confidence`.
CHARACTER_ADVANCEMENT = CharacterAdvancementLayout()


@dataclass(frozen=True)
class GameTableLayout:
    key: str
    source_dbc: str
    physical_form: str          # "implicit_row" | "explicit_id"
    key_source: str             # "ordinal" | "explicit_id"
    expected_field_count: int
    expected_record_size: int
    value_cell: int
    id_cell: int | None
    index_kind: str             # rating_by_level | class_rating_scalar | class_by_level | class_only
    axes: tuple[str, ...]
    class_indexed: bool
    supported: dict
    index_offset: int = 0
    semantics: str = "proven"


# ChrClasses is a normal named DBC, NOT a GameTable. Pinned 3.3.5a columns: ClassID @0,
# powerType @2, first localized (enUS) name @5.
CHR_CLASSES = DbcLayout(
    name="ChrClasses", expected_field_count=60, expected_record_size=60 * 4,
    columns={"id": FieldSpec(0, "uint32"), "power_type": FieldSpec(2, "int32"),
             "name": FieldSpec(5, "str")},
)
