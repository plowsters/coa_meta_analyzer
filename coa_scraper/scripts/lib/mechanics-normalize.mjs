// WotLK 3.3.5a spell school mask bits (validated against observed CoA data by the recon test).
// Serialized in ascending bit order — order is documentation, NOT priority.
export const SCHOOL_MASK_BITS = Object.freeze({
  1: "physical", 2: "holy", 4: "fire", 8: "nature", 16: "frost", 32: "shadow", 64: "arcane",
});

// Spell.dbc PowerType enum → resource name.
export const POWER_TYPE_MAP = Object.freeze({
  "-2": "health", "0": "mana", "1": "rage", "2": "focus", "3": "energy",
  "4": "happiness", "5": "runes", "6": "runic_power",
});

// Legitimate numeric sentinels that must be preserved, not treated as parse errors.
export const DURATION_SENTINELS = Object.freeze({ INFINITE: -1 });

export function isPresent(value) {
  return value !== null && value !== undefined;
}

// mask → { schools: string[], unknownBits: number[] }. Absent mask → empty schools, no unknowns.
export function normalizeSchoolMask(mask) {
  if (!isPresent(mask)) return { schools: [], unknownBits: [] };
  const schools = [];
  const unknownBits = [];
  for (let bit = 1; bit <= mask && bit > 0; bit <<= 1) {
    if ((mask & bit) === 0) continue;
    const name = SCHOOL_MASK_BITS[bit];
    if (name) schools.push(name);
    else unknownBits.push(bit);
  }
  return { schools, unknownBits };
}

// int → { value: string|null, unknown: boolean }. Absent → { value: null, unknown: false }.
export function normalizePowerType(powerType) {
  if (!isPresent(powerType)) return { value: null, unknown: false };
  const name = POWER_TYPE_MAP[String(powerType)];
  return name ? { value: name, unknown: false } : { value: null, unknown: true };
}

// -1 (infinite) is preserved; absent → null.
export function normalizeDurationMs(ms) {
  if (!isPresent(ms)) return null;
  return ms;
}
