import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.client

REPO = Path(__file__).resolve().parents[1]
CLIENT_ROOT = Path(os.environ.get(
    "COA_CLIENT_ROOT",
    str(Path.home() / "Games/ascension-wow/drive_c/Program Files/Ascension Launcher/resources/ascension-live/Data"),
))


def _mechanics_recon(client_root, tmp_path, spell_policy=None):
    from coa_client_extract.cli import mechanics_recon_command
    from coa_client_extract.errors import BackendUnavailable
    try:
        return mechanics_recon_command(client_root, tmp_path, spell_policy=spell_policy)
    except BackendUnavailable:
        pytest.skip("StormLib not available")


@pytest.mark.skipif(not CLIENT_ROOT.is_dir(), reason="Ascension client not installed at COA_CLIENT_ROOT")
def test_committed_policy_verifies_against_real_client(tmp_path):
    # The committed, reviewed, client-bound policy re-verifies against the real client: anchors are
    # uniquely re-discovered at their policy cells, SpellEffect is absent (inline effects), no blocking.
    report = _mechanics_recon(CLIENT_ROOT, tmp_path)
    assert report["status"] == "verified", report["blocking_findings"]
    assert report["blocking_findings"] == []
    assert report["layout_proof"]["power_type"]["discovered_cell"] == 41
    assert report["layout_proof"]["power_type"]["matches_policy"] is True
    assert report["layout_proof"]["school_mask"]["discovered_cell"] == 225
    assert report["layout_proof"]["name"]["discovered_cell"] == 136
    assert report["topology"]["SpellEffect"]["present"] is False
    assert report["topology"]["SpellCooldowns"]["present"] is False


@pytest.mark.skipif(not CLIENT_ROOT.is_dir(), reason="Ascension client not installed at COA_CLIENT_ROOT")
def test_unbound_policy_is_review_required_and_proposes_the_delta(tmp_path):
    # An intentionally-unbound variant (reviewed cleared, bound nulled) can never reach `verified`; recon
    # discovers the cells by scanning and PROPOSES them (it never writes the policy). This documents the
    # one-time manual adjudication procedure: review proposed_policy_delta -> author cells + bound ->
    # flip reviewed. (See docs/data/spell-mechanics-recon-schema.md.)
    from coa_client_extract.spell_layout import compute_policy_sha256, load_spell_policy
    payload = json.loads((REPO / "coa_client_extract/data/spell_layout_v1.json").read_text())
    payload["reviewed"] = False
    payload["bound"] = None
    payload["sha256"] = compute_policy_sha256(payload)
    unbound = load_spell_policy(payload)

    report = _mechanics_recon(CLIENT_ROOT, tmp_path, spell_policy=unbound)
    assert report["status"] == "review_required"
    assert report["blocking_findings"] == []
    assert report["proposed_policy_delta"]["power_type"] == 41
    assert report["proposed_policy_delta"]["school_mask"] == 225
    assert report["proposed_policy_delta"]["name"] == 136
