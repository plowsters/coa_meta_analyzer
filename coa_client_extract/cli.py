from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .archive_backend import ArchiveBackend
from .archive_plan import discover_plan
from .artifacts import build_client_spell_records, write_json, write_jsonl
from .content_json import read_content_records
from .dbc_layouts import SPELL_FAMILY
from .errors import BackendUnavailable
from .manifest import build_manifest
from .wdbc import DbcLayout, parse_dbc


def regenerate(
    client_root: Path,
    out_dir: Path,
    *,
    backend: ArchiveBackend | None = None,
    stormlib_path: str | None = None,
    layouts: dict[str, DbcLayout] | None = None,
) -> dict:
    if backend is None:
        from .stormlib_backend import StormLibBackend
        backend = StormLibBackend(stormlib_path=stormlib_path)  # may raise BackendUnavailable

    plan = discover_plan(client_root)
    layouts = layouts or SPELL_FAMILY
    root, attach = plan.open_chain  # StormLib root + all base+patch archives attached on top

    def read_table(name: str):
        member = backend.read_effective_file(root, attach, f"DBFilesClient\\{name}.dbc")
        return member, parse_dbc(member.data, layouts[name])

    spell_member, spell = read_table("Spell")
    _, cast = read_table("SpellCastTimes")
    _, dur = read_table("SpellDuration")
    _, rng = read_table("SpellRange")

    provenance = {
        "base_archive": spell_member.base_archive.name,
        "patch_chain": [p.name for p in spell_member.patch_chain],
        "effective_archive": spell_member.effective_archive.name,
        "source_dbcs": {"Spell": spell_member.effective_archive.name},
        "extraction_date": date.today().isoformat(),
    }

    spell_records = build_client_spell_records(spell, cast, dur, rng, provenance=provenance)
    content_records = read_content_records(client_root / "Content")

    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "coa_client_spell.jsonl": write_jsonl(spell_records, out_dir / "coa_client_spell.jsonl"),
        "coa_client_content.jsonl": write_jsonl(content_records, out_dir / "coa_client_content.jsonl"),
        "coa_client_archive_plan.json": write_json(plan.to_dict(), out_dir / "coa_client_archive_plan.json"),
    }
    manifest = build_manifest(
        backend_name=getattr(backend, "name", "unknown"),
        backend_version=getattr(backend, "version", "unknown"),
        stormlib_version=None,
        client_root=str(client_root),
        client_build="unknown",
        outputs=outputs,
        archive_plan=plan.to_dict(),
    )
    write_json(manifest, out_dir / "coa_client_extract_manifest.json")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coa_client_extract")
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("regenerate", help="extract client artifacts")
    reg.add_argument("--client-root", required=True, type=Path)
    reg.add_argument("--out", required=True, type=Path)
    reg.add_argument("--stormlib", default=None)
    args = parser.parse_args(argv)

    if args.command == "regenerate":
        try:
            regenerate(args.client_root, args.out, stormlib_path=args.stormlib)
        except BackendUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0
    return 1
