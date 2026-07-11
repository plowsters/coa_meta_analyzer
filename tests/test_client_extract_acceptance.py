import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.client

CLIENT_ROOT = Path(os.environ.get(
    "COA_CLIENT_ROOT",
    str(Path.home() / "Games/ascension-wow/drive_c/Program Files/Ascension Launcher/resources/ascension-live/Data"),
))


@pytest.mark.skipif(not CLIENT_ROOT.is_dir(), reason="Ascension client not installed at COA_CLIENT_ROOT")
def test_spell_805775_is_current_adrenal_venom(tmp_path):
    from coa_client_extract.cli import regenerate
    from coa_client_extract.errors import BackendUnavailable

    try:
        manifest = regenerate(CLIENT_ROOT, tmp_path)  # real StormLib backend, real layouts
    except BackendUnavailable:
        pytest.skip("StormLib not available")

    assert manifest["schema_version"] == "coa-client-extract-manifest-v1"

    rows = [json.loads(line) for line in (tmp_path / "coa_client_spell.jsonl").read_text().splitlines()]
    by_id = {r["spell_id"]: r for r in rows}
    assert 805775 in by_id, "spell 805775 not extracted"
    venom = by_id[805775]
    assert "Adrenal Venom" in venom["name"]
    assert "Fang Venom" not in venom["name"]  # not the stale db value
    assert venom["provenance"]["schema_match_confidence"] in ("high", "low")
    assert venom["coa_attribution"]["status"] == "unknown"  # attribution is M1.14B
