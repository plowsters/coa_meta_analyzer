from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssetResolver:
    asset_root: Path | None = None

    def class_tree_image(self, class_name: str) -> str | None:
        if self.asset_root is None:
            return None
        root = Path(self.asset_root)
        if not root.exists():
            return None
        slug = _asset_slug(class_name)
        for path in root.rglob("*"):
            lowered = path.name.lower()
            if path.is_file() and slug in lowered and lowered.endswith((".webp", ".png", ".jpg", ".jpeg")):
                return str(path)
        return None

    def node_icon(self, icon: str | None) -> str | None:
        if not icon or self.asset_root is None:
            return None
        root = Path(self.asset_root)
        if not root.exists():
            return None
        icon_slug = _asset_slug(icon.split("\\")[-1])
        for path in root.rglob("*"):
            lowered = path.stem.lower()
            if path.is_file() and icon_slug and icon_slug in lowered:
                return str(path)
        return None


def _asset_slug(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())
