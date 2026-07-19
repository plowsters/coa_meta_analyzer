from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from .manifest import build_manifest_v2

POINTER_SCHEMA = "coa-client-extract-pointer-v1"
POINTER_NAME = "coa_client_extract.pointer.json"
MANIFEST_NAME = "manifest.json"
_RESERVED = {MANIFEST_NAME, POINTER_NAME}


class PublishError(Exception):
    """A generation could not be staged/published (bad child name, collision, or staging failure)."""


class ResolveError(Exception):
    """The active generation pointer failed validation (schema, containment, hash, or a child mismatch).
    Fails closed — a consumer never reads an unvalidated generation child."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_child_name(name: str) -> None:
    if not name or name in _RESERVED:
        raise PublishError(f"reserved or empty child name {name!r}")
    if os.path.isabs(name) or ".." in Path(name).parts or "/" in name or "\\" in name:
        raise PublishError(f"unsafe child name {name!r} (no absolute/traversal/separators)")


class GenerationWriter:
    """Stages a new immutable generation under `root/gen-<uuid4>/` (exist_ok=False so two concurrent
    publishers never collide), streams each child to a temp file while hashing + counting it, then on
    publish writes the binding manifest and finally a validated pointer LAST."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.generation_id = uuid.uuid4().hex
        self.gen_dir = self.root / f"gen-{self.generation_id}"
        self.gen_dir.mkdir(exist_ok=False)          # collision-safe; a reused id raises FileExistsError
        self._children: dict[str, dict] = {}

    def _stage(self, name: str, body: bytes, records: int, schema_version: str) -> None:
        _safe_child_name(name)
        if name in self._children:
            raise PublishError(f"duplicate child {name!r}")
        if not schema_version:
            raise PublishError(f"child {name!r} needs a non-empty schema_version")
        tmp = self.gen_dir / f".{name}.tmp-{os.getpid()}"
        tmp.write_bytes(body)
        os.replace(tmp, self.gen_dir / name)
        self._children[name] = {"sha256": _sha256(body), "byte_length": len(body),
                                "records": records, "schema_version": schema_version}

    def add_jsonl(self, name: str, records: list[dict], *, schema_version: str) -> None:
        body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode("utf-8")
        self._stage(name, body, len(records), schema_version)

    def add_json(self, name: str, doc: dict, *, schema_version: str) -> None:
        body = (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self._stage(name, body, 1, schema_version)   # a non-JSONL child is defined as records == 1

    def _predecessor(self) -> str | None:
        pointer = self.root / POINTER_NAME
        if not pointer.is_file():
            return None
        try:
            return json.loads(pointer.read_text(encoding="utf-8")).get("generation_id")
        except (ValueError, OSError):
            return None

    def publish(self, *, base_manifest: dict, binding: dict, unknown_symbol_inventory: dict) -> dict:
        manifest = build_manifest_v2(
            base=base_manifest, generation_id=self.generation_id, published_at=time.time_ns(),
            predecessor_generation_id=self._predecessor(), children=dict(self._children),
            unknown_symbol_inventory=unknown_symbol_inventory, binding=binding)
        manifest_body = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        # manifest is generation-local + immutable; write it inside the (unique) gen dir.
        (self.gen_dir / MANIFEST_NAME).write_bytes(manifest_body)

        pointer = {"schema_version": POINTER_SCHEMA, "generation_id": self.generation_id,
                   "manifest_path": f"gen-{self.generation_id}/{MANIFEST_NAME}",
                   "manifest_sha256": _sha256(manifest_body)}
        pointer_body = (json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        tmp = self.root / f".{POINTER_NAME}.tmp-{os.getpid()}"
        tmp.write_bytes(pointer_body)
        os.replace(tmp, self.root / POINTER_NAME)    # atomic publish of the pointer, LAST
        return manifest


def resolve_active_generation(root: Path) -> dict:
    """Validate and resolve the active generation the pointer names. Fails closed (ResolveError) on any
    mismatch: pointer schema, gen-dir containment, manifest hash, or a child's path/sha256/bytes/records/
    schema/uniqueness. Returns {generation_id, gen_dir, manifest, children:{name: Path}}."""
    root = Path(root)
    pointer_path = root / POINTER_NAME
    if not pointer_path.is_file():
        raise ResolveError("no active generation pointer")
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ResolveError(f"pointer is not valid JSON: {exc}") from exc
    if pointer.get("schema_version") != POINTER_SCHEMA:
        raise ResolveError(f"pointer bad schema_version {pointer.get('schema_version')!r}")

    gen_id = pointer.get("generation_id")
    if not isinstance(gen_id, str) or not gen_id:
        raise ResolveError("pointer missing generation_id")
    gen_dir = (root / f"gen-{gen_id}").resolve()
    if os.path.commonpath([gen_dir, root.resolve()]) != str(root.resolve()):
        raise ResolveError("generation directory escapes the root")
    manifest_path = gen_dir / MANIFEST_NAME
    if manifest_path.resolve().parent != gen_dir:
        raise ResolveError("manifest path escapes the generation directory")
    if not manifest_path.is_file():
        raise ResolveError("generation manifest missing")

    manifest_body = manifest_path.read_bytes()
    if _sha256(manifest_body) != pointer.get("manifest_sha256"):
        raise ResolveError("manifest sha256 does not match the pointer")
    manifest = json.loads(manifest_body)
    if manifest.get("generation_id") != gen_id:
        raise ResolveError("manifest generation_id disagrees with the pointer")

    children = manifest.get("children", {})
    resolved: dict[str, Path] = {}
    seen: set[str] = set()
    for name, meta in children.items():
        _safe_name_resolve(name)
        if name in seen:
            raise ResolveError(f"duplicate child {name!r}")
        seen.add(name)
        child_path = (gen_dir / name).resolve()
        if child_path.parent != gen_dir:
            raise ResolveError(f"child {name!r} escapes the generation directory")
        if not child_path.is_file():
            raise ResolveError(f"child {name!r} missing")
        body = child_path.read_bytes()
        if _sha256(body) != meta.get("sha256"):
            raise ResolveError(f"child {name!r} sha256 mismatch")
        if len(body) != meta.get("byte_length"):
            raise ResolveError(f"child {name!r} byte_length mismatch")
        actual_records = sum(1 for line in body.splitlines() if line.strip()) if name.endswith(".jsonl") else 1
        if actual_records != meta.get("records"):
            raise ResolveError(f"child {name!r} record count mismatch ({actual_records} != {meta.get('records')})")
        if not meta.get("schema_version"):
            raise ResolveError(f"child {name!r} missing schema_version")
        resolved[name] = child_path
    return {"generation_id": gen_id, "gen_dir": gen_dir, "manifest": manifest, "children": resolved}


def _safe_name_resolve(name: str) -> None:
    if not name or name in _RESERVED or os.path.isabs(name) or ".." in Path(name).parts \
            or "/" in name or "\\" in name:
        raise ResolveError(f"unsafe child name {name!r}")


def prune_generations(root: Path, *, grace_seconds: float, quiescent: bool = False,
                      now_ns: int | None = None) -> dict:
    """Best-effort retention (a SEPARATE maintenance op — publish never prunes). Keep the pointer's
    current target and its immediate predecessor (via `predecessor_generation_id`, so a random-UUID +
    date-only manifest can still identify the chain). Older `gen-*` are removed only when `quiescent`
    is set (an enforced quiescent window / advisory lock) AND they are older than `grace_seconds`.
    Without quiescence, deletes NOTHING and returns the plan (documented best-effort)."""
    root = Path(root)
    now_ns = now_ns if now_ns is not None else time.time_ns()
    active = resolve_active_generation(root)          # fails closed if the pointer is invalid
    keep = {active["generation_id"]}
    predecessor = active["manifest"].get("predecessor_generation_id")
    if predecessor:
        keep.add(predecessor)

    candidates, removed = [], []
    for d in sorted(root.glob("gen-*")):
        if not d.is_dir():
            continue
        gid = d.name[len("gen-"):]
        if gid in keep:
            continue
        published_at = _read_published_at(d)
        age_s = (now_ns - published_at) / 1e9 if published_at is not None else float("inf")
        if age_s <= grace_seconds:
            continue
        candidates.append(d.name)
        if quiescent:
            shutil.rmtree(d)
            removed.append(d.name)
    return {"kept": sorted(keep), "removed": removed, "prunable": candidates, "quiescent": quiescent}


def _read_published_at(gen_dir: Path) -> int | None:
    try:
        return json.loads((gen_dir / MANIFEST_NAME).read_text(encoding="utf-8")).get("published_at")
    except (ValueError, OSError):
        return None
