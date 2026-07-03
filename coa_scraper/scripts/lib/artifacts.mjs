import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export function repoRelative(filePath, rootDir = process.cwd()) {
  return path.relative(rootDir, filePath).replaceAll(path.sep, "/");
}

export function assertFile(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Required file does not exist: ${filePath}`);
  }
}

export function sha256File(filePath) {
  assertFile(filePath);
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

export function artifactRecord(filePath, rootDir = process.cwd()) {
  assertFile(filePath);
  const stat = fs.statSync(filePath);
  return {
    path: repoRelative(filePath, rootDir),
    bytes: stat.size,
    sha256: sha256File(filePath)
  };
}

export function loadJson(filePath) {
  assertFile(filePath);
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (err) {
    throw new Error(`Invalid JSON in ${filePath}: ${err.message}`);
  }
}

export function loadJsonl(filePath) {
  assertFile(filePath);
  const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
  const records = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    try {
      records.push(JSON.parse(line));
    } catch (err) {
      throw new Error(`Invalid JSONL in ${filePath}:${i + 1}: ${err.message}`);
    }
  }
  return records;
}

export function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}
