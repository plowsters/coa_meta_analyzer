import json
import re
from pathlib import Path

import pytest

NORMALIZE = Path("coa_scraper/scripts/lib/mechanics-normalize.mjs")
PROJECTION = Path("reports/client_extract/coa_client_spell_coa.jsonl")


def _documented():
    text = NORMALIZE.read_text(encoding="utf-8")
    bits = set(int(m) for m in re.findall(r'(\d+):\s*"', text.split("SCHOOL_MASK_BITS")[1].split("}")[0]))
    powers = set(int(m) for m in re.findall(r'"(-?\d+)":\s*"', text.split("POWER_TYPE_MAP")[1].split("}")[0]))
    return bits, powers


@pytest.mark.client
def test_observed_enums_covered_by_documented_maps():
    if not PROJECTION.is_file():
        pytest.skip("projection not present (client tier)")
    bits, powers = _documented()
    seen_bits, seen_powers = set(), set()
    for line in PROJECTION.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        mech = json.loads(line).get("mechanics", {})
        mask = mech.get("school_mask")
        if isinstance(mask, int) and mask > 0:
            b = 1
            while b <= mask:
                if mask & b:
                    seen_bits.add(b)
                b <<= 1
        pt = mech.get("power_type")
        if isinstance(pt, int):
            seen_powers.add(pt)
    assert seen_bits <= bits, f"undocumented school-mask bits: {sorted(seen_bits - bits)}"
    assert seen_powers <= powers, f"undocumented power_type values: {sorted(seen_powers - powers)}"
