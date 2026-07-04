import fs from "node:fs";
import path from "node:path";

const DB_HOST = "https://db.ascension.gg";

export function powerUrl(kind, id) {
  if (kind !== "spell" && kind !== "item") {
    throw new Error(`Unsupported AscensionDB kind: ${kind}`);
  }
  return `${DB_HOST}/?${kind}=${id}&power`;
}

export function stripTooltipHtml(html) {
  return String(html || "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

export function extractLinkedIds(html, kind) {
  const rx = new RegExp(`href=["']\\?${kind}=(\\d+)["']`, "g");
  const ids = [];
  for (const match of String(html || "").matchAll(rx)) {
    const id = Number(match[1]);
    if (Number.isFinite(id) && !ids.includes(id)) {
      ids.push(id);
    }
  }
  return ids;
}

export function extractTooltipLevel(text) {
  const match = String(text || "").match(/\bLevel\s+(\d+)\b/i);
  return match ? Number(match[1]) : null;
}

function parseRegisterCall(payload, expectedKind, expectedId) {
  const kindName = expectedKind === "spell" ? "registerSpell" : "registerItem";
  const rx = new RegExp(`\\$WowheadPower\\.${kindName}\\((\\d+),\\s*(\\d+),\\s*([\\s\\S]*)\\);\\s*$`);
  const match = String(payload || "").trim().match(rx);
  if (!match) {
    return null;
  }

  const id = Number(match[1]);
  if (id !== Number(expectedId)) {
    throw new Error(`AscensionDB payload id ${id} did not match requested id ${expectedId}`);
  }

  return JSON.parse(match[3]);
}

export function parsePowerPayload(payload, { kind, id, url, fetchedAt = new Date().toISOString() }) {
  const data = parseRegisterCall(payload, kind, id);
  if (data === null) {
    return {
      kind,
      id,
      status: "not_found",
      name: null,
      icon: null,
      tooltip_html: "",
      tooltip_text: "",
      tooltip_level: null,
      required_level: null,
      linked_spell_ids: [],
      linked_item_ids: [],
      raw: String(payload || ""),
      provenance: { url, fetched_at: fetchedAt }
    };
  }

  if (Object.keys(data).length === 0) {
    return {
      kind,
      id,
      status: "empty_registration",
      name: null,
      icon: null,
      tooltip_html: "",
      tooltip_text: "",
      tooltip_level: null,
      required_level: null,
      linked_spell_ids: [],
      linked_item_ids: [],
      raw: data,
      provenance: { url, fetched_at: fetchedAt }
    };
  }

  const tooltipHtml = data.tooltip_enus || "";
  const tooltipText = stripTooltipHtml(tooltipHtml);
  const tooltipLevel = extractTooltipLevel(tooltipText);
  const requiredLevelMatch = tooltipText.match(/\bRequires Level\s+(\d+)\b/i);

  return {
    kind,
    id,
    status: "matched",
    name: data.name_enus || null,
    icon: data.icon || null,
    quality: data.quality ?? null,
    tooltip_html: tooltipHtml,
    tooltip_text: tooltipText,
    tooltip_level: tooltipLevel,
    required_level: requiredLevelMatch ? Number(requiredLevelMatch[1]) : tooltipLevel,
    linked_spell_ids: extractLinkedIds(tooltipHtml, "spell"),
    linked_item_ids: extractLinkedIds(tooltipHtml, "item"),
    buff_tooltip_html: data.buff_enus || "",
    raw: data,
    provenance: { url, fetched_at: fetchedAt }
  };
}

export function readJsonl(filePath) {
  if (!fs.existsSync(filePath)) {
    return [];
  }
  const text = fs.readFileSync(filePath, "utf8").trim();
  if (!text) {
    return [];
  }
  return text.split("\n").filter(Boolean).map(line => JSON.parse(line));
}

export function writeJsonl(filePath, rows) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${rows.map(row => JSON.stringify(row)).join("\n")}\n`);
}
