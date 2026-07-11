from __future__ import annotations

from pathlib import Path

from .archive_backend import ExtractedMember
from . import stormlib_ctypes as sl


class StormLibBackend:
    name = "stormlib_ctypes"
    version = "coa-stormlib-v1"

    def __init__(self, stormlib_path: str | None = None):
        # Raises BackendUnavailable (fail closed) if the library cannot be loaded.
        self._lib = sl.load_stormlib(stormlib_path)
        # Pin the loaded library identity for the manifest (Decision 20).
        self.stormlib_version = sl.resolve_version(self._lib)

    def read_effective_file(
        self, base_archive: Path, patch_archives: tuple[Path, ...], logical_path: str
    ) -> ExtractedMember:
        data, chain_paths = sl.read_effective_member(
            self._lib, base_archive, patch_archives, logical_path
        )
        # StormLib reports the participating archives as filesystem paths. Map them back to
        # the plan's Path objects by basename (archive names are unique within a plan) so
        # provenance is expressed in the caller's own vocabulary. This is the REAL winning
        # chain, not the attach order — the effective archive is the last participant.
        known = {p.name: p for p in (base_archive, *patch_archives)}
        chain = tuple(known.get(Path(cp).name, Path(cp)) for cp in chain_paths)
        if chain:
            effective_archive = chain[-1]
        else:
            # StormLib declined to report a chain (should not happen for a present file);
            # fall back to the full attach order rather than fabricating a single winner.
            chain = (base_archive, *patch_archives)
            effective_archive = patch_archives[-1] if patch_archives else base_archive
        return ExtractedMember(
            logical_path=logical_path,
            data=data,
            base_archive=base_archive,
            patch_chain=chain,
            effective_archive=effective_archive,
            backend_name=self.name,
            backend_version=self.version,
        )

    def has_file(
        self, base_archive: Path, patch_archives: tuple[Path, ...], logical_path: str
    ) -> bool:
        return sl.member_exists(self._lib, base_archive, patch_archives, logical_path)
