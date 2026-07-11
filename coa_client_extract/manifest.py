from __future__ import annotations

from datetime import date


def build_manifest(
    *,
    backend_name: str,
    backend_version: str,
    stormlib_version: str | None,
    client_root: str,
    client_build: str,
    outputs: dict[str, str],
    archive_plan: dict,
) -> dict:
    return {
        "schema_version": "coa-client-extract-manifest-v1",
        "wrapper_version": "coa-stormlib-v1",
        "backend": backend_name,
        "backend_version": backend_version,
        "stormlib_version": stormlib_version,
        "client_root": client_root,
        "client_build": client_build,
        "extraction_date": date.today().isoformat(),
        "archive_plan": archive_plan,
        "outputs": outputs,
    }
