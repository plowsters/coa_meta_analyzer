// coa-mechanics-v2: the canonical Node builder writes cooldown/gcd/costs as explicit null (unknown) with
// a readiness reason — never a defaulted 0/1500/{} — and the row is accepted by the Python v2 loader.
import { test } from "node:test";
import assert from "node:assert";
import { execFileSync } from "node:child_process";
import { buildCanonicalMechanics } from "../scripts/build-mechanics-artifacts.mjs";

function oneRow() {
  const projection = [{
    spell_id: 92117, name: "Adrenal Venom",
    mechanics: { school_mask: 8, power_type: 3, cast_time_ms: 0, duration_ms: 12000, range_min_yd: 0, range_max_yd: 30 },
    coa_attribution: { is_coa: true, confidence: "high" },
  }];
  const entry = { spell_id: 92117, entry_id: 1, entry_type: "Ability", name: "Adrenal Venom", damage_schools: ["nature"], resources: ["energy"], tags: ["damage"] };
  return buildCanonicalMechanics({ entries: [entry], spellRows: [], projection })[0];
}

test("the builder emits coa-mechanics-v2 with null cooldown/gcd/costs (missing != default)", () => {
  const row = oneRow();
  assert.equal(row.schema_version, "coa-mechanics-v2");
  assert.equal(row.cooldown_ms, null);
  assert.equal(row.gcd_ms, null);
  assert.equal(row.costs, null);                    // unknown, NOT {}
});

test("null cooldown/gcd/costs each carry an explicit readiness reason", () => {
  const row = oneRow();
  for (const f of ["cooldown_ms", "gcd_ms", "costs"]) {
    assert.equal(row.field_readiness[f].status, "unavailable");
    assert.equal(row.field_readiness[f].reason_code, "pending_e1_operand");
  }
});

test("a v2 row round-trips through the Python coa-mechanics-v2 loader", () => {
  const row = oneRow();
  const py = [
    "import json,sys",
    "from coa_meta.mechanics import mechanic_from_raw",
    "r = mechanic_from_raw(json.loads(sys.argv[1]))",
    "assert r.costs is None, r.costs",
    "assert r.field_readiness['costs']['status'] == 'unavailable'",
    "print('ok')",
  ].join("\n");
  const out = execFileSync("python3", ["-c", py, JSON.stringify(row)], { encoding: "utf8" });
  assert.match(out, /ok/);
});
