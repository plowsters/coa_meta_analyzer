from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .archive_backend import ArchiveBackend, ExtractedMember
from .errors import ArchiveError

ORDERING_RULE = "coa-archive-order-v1"
_BASE = ("common", "common-2", "expansion", "lichking")
_NUMERIC_PATCH = re.compile(r"^patch(-\d+)?$", re.IGNORECASE)
_COA_PATCH = re.compile(r"^patch-C[A-Z0-9]*$", re.IGNORECASE)   # patch-C, patch-CA … patch-CZZ
# Warcraft Reborn/Bronzebeard. The suffix may carry digits (patch-WB1, patch-WC3), so the
# class must allow them — a bare [A-Z]* silently mis-included the digit variants in the CoA
# chain against Decision 18. Verified against the real client's patch-W* set.
_REBORN_PATCH = re.compile(r"^patch-W[A-Z0-9]*$", re.IGNORECASE)
_ANY_PATCH = re.compile(r"^patch(-[0-9A-Za-z]+)?$", re.IGNORECASE)


@dataclass(frozen=True)
class ArchivePlan:
    client_root: Path
    base_archives: tuple[Path, ...]
    patch_archives: tuple[Path, ...]
    excluded: dict[str, tuple[Path, ...]]
    ordering_rule: str = ORDERING_RULE

    def to_dict(self) -> dict:
        return {
            "schema_version": "coa-client-archive-plan-v1",
            "client_root": str(self.client_root),
            "ordering_rule": self.ordering_rule,
            "base_archives": [p.name for p in self.base_archives],
            "patch_archives": [p.name for p in self.patch_archives],
            "excluded": {k: [p.name for p in v] for k, v in self.excluded.items()},
        }

    @property
    def open_chain(self) -> tuple[Path, tuple[Path, ...]]:
        # StormLib root archive plus every other base + patch archive attached on top, in load order.
        if not self.base_archives:
            raise ArchiveError(f"no base archive found under {self.client_root}")
        root, *rest = self.base_archives
        return root, (*rest, *self.patch_archives)


def _patch_sort_key(name: str) -> tuple:
    stem = name.rsplit(".", 1)[0]
    if _NUMERIC_PATCH.match(stem):
        # group 0: base patches — plain "patch" first, then patch-2, patch-3
        parts = stem.split("-")
        num = int(parts[1]) if len(parts) > 1 else 0
        return (0, num, "")
    if _COA_PATCH.match(stem):
        # group 2: CoA family loads last (highest priority) — C, CA, CB … CZ < CZZ
        letters = stem.split("-", 1)[1][1:]  # drop the leading 'C'
        return (2, len(letters), letters.upper())
    # group 1: other Ascension patches (patch-A, patch-B, patch-I, patch-M, …)
    suffix = stem.split("-", 1)[1] if "-" in stem else ""
    return (1, len(suffix), suffix.upper())


def discover_plan(client_root: Path) -> ArchivePlan:
    archives = sorted(p for p in client_root.glob("*.MPQ"))
    archives += sorted(p for p in client_root.glob("*.mpq"))
    by_name = {p.name.rsplit(".", 1)[0].lower(): p for p in archives}

    base = tuple(by_name[n] for n in _BASE if n in by_name)
    patches: list[Path] = []
    reborn: list[Path] = []
    for p in archives:
        stem = p.name.rsplit(".", 1)[0]
        if stem.lower() in _BASE:
            continue
        if _REBORN_PATCH.match(stem):
            reborn.append(p)  # Warcraft Reborn — excluded from the CoA chain
        elif _ANY_PATCH.match(stem):
            patches.append(p)  # base Ascension + CoA patches load together; attribution is M1.14B
    patches.sort(key=lambda p: _patch_sort_key(p.name))

    area52_dir = client_root / "area-52"
    area52 = (
        tuple(sorted(area52_dir.glob("*.MPQ")) + sorted(area52_dir.glob("*.mpq")))
        if area52_dir.is_dir()
        else ()
    )

    return ArchivePlan(
        client_root=client_root,
        base_archives=base,
        patch_archives=tuple(patches),
        excluded={"area52": area52, "reborn": tuple(reborn)},
    )


def family_of(archive_name: str) -> str:
    """Classify an archive filename into its CoA-relevant family. This is a raw provenance
    signal only — M1.14B decides attribution from it, not M1.14A. Families: ``coa`` for the
    patch-C* line, ``reborn`` for the excluded patch-W* line, ``base`` for the four stock
    WotLK archives, and ``other`` for base-game Ascension patches whose family is undecided."""
    stem = archive_name.rsplit(".", 1)[0]
    if _COA_PATCH.match(stem):
        return "coa"
    if _REBORN_PATCH.match(stem):
        return "reborn"
    if stem.lower() in _BASE:
        return "base"
    return "other"


def validate_ordering(
    plan: ArchivePlan, backend: ArchiveBackend, logical_path: str, expected_effective: Path
) -> None:
    root, attach = plan.open_chain
    member = backend.read_effective_file(root, attach, logical_path)
    if member.effective_archive.name != expected_effective.name:
        raise ArchiveError(
            f"archive-plan ordering mismatch for {logical_path}: resolved "
            f"{member.effective_archive.name}, expected {expected_effective.name}"
        )


def validate_load_order(plan: ArchivePlan, member: ExtractedMember) -> None:
    """Fail closed if an extracted member's provenance is inconsistent with the plan's
    declared load order. Two invariants must hold before any canonical artifact is written:
    every archive that supplied bytes must be a member of the plan, and the winning
    (effective) archive must be the highest-priority supplier under the plan's load order.
    This proves the order StormLib actually applied matches the order CoA Codex declared —
    the exit criterion that ordering is validated against a real overridden table."""
    root, attach = plan.open_chain
    priority = {p.name: i for i, p in enumerate((root, *attach))}
    for archive in (*member.patch_chain, member.effective_archive):
        if archive.name not in priority:
            raise ArchiveError(
                f"{member.logical_path}: supplier {archive.name} is not part of the archive "
                f"plan; refusing to emit canonical artifacts"
            )
    winner = priority[member.effective_archive.name]
    for archive in member.patch_chain:
        if priority[archive.name] > winner:
            raise ArchiveError(
                f"{member.logical_path}: load order inverted — {archive.name} outranks the "
                f"winning archive {member.effective_archive.name}"
            )
