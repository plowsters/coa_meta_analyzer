from __future__ import annotations


class ExtractError(Exception):
    """Base class for all client-extraction failures."""


class BackendUnavailable(ExtractError):
    """The archive backend (e.g. StormLib) could not be loaded/opened."""


class ArchiveError(ExtractError):
    """An archive or logical file could not be resolved through the plan."""


class DbcDriftError(ExtractError):
    """A DBC header disagreed with its declared layout beyond tolerance."""


class DbcSemanticError(ExtractError):
    """A DBC column layout matched its WDBC header but failed semantic validation
    (foreign keys, adjacency domain, or value ranges). Distinct from DbcDriftError,
    which is a structural header mismatch."""


class ClientBindingError(ExtractError):
    """The spell-layout policy is not reviewed, or its `bound` client bytes/build do not match the
    opened client. Canonical v2 emission fails closed (CLI exit 3) rather than promote values proven
    against a different client."""
