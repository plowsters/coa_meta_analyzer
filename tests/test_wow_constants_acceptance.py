import json
import os
from pathlib import Path

import pytest

from coa_client_extract.cli import wow_constants_command
from coa_meta.wow_constants import WowConstantsRepository

CLIENT_ROOT = Path(os.environ.get("COA_CLIENT_ROOT", "/nonexistent"))


@pytest.mark.client
@pytest.mark.skipif(not CLIENT_ROOT.is_dir(), reason="Ascension client not installed at COA_CLIENT_ROOT")
def test_real_client_snapshot_is_structurally_sound(tmp_path):
    out = tmp_path / "out"
    manifest = wow_constants_command(CLIENT_ROOT, out)
    repo = WowConstantsRepository.load(out / "coa_wow_constants.json")
    assert manifest["class_context_resolution"] in ("unproven", "actor_wow_class_id", "versioned_bridge")
    assert repo.combat_rating_ratio(10, 60) > 0                     # context-free lookup resolves
    snap = json.loads((out / "coa_wow_constants.json").read_text())
    rc = snap["game_tables"]["combat_ratings"]["reference_comparison"]
    # anchors are table-tagged raw combat_ratings values -> they ARE checked (never no_anchors_checked)
    assert rc["status"] in ("matches_on_checked_anchors", "differs_on_checked_anchors")
