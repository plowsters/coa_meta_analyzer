# AscensionDB Cache Manifest Schema

Schema version: `coa-ascensiondb-cache-manifest-v1`

The AscensionDB cache manifest records the fetch and parse state for every external URL used by the scraper. The report generator must consume local artifacts only; generated guide pages must not fetch AscensionDB at page load or tooltip hover time.

## Manifest File

The manifest is a JSON object:

```json
{
  "schema_version": "coa-ascensiondb-cache-manifest-v1",
  "resources": []
}
```

`resources` is an array of cache rows.

## Cache Row Fields

- `cache_key`: SHA-256 hash of the URL, used for deterministic file naming.
- `url`: source URL.
- `resource_kind`: resource category such as `spell`, `item`, `effect`, or `icon`.
- `source_kind`: seed source category, usually `spell`, `item`, or `linked_spell`.
- `source_id`: numeric spell or item ID when applicable.
- `parser_version`: parser version that produced the parsed artifact.
- `status`: cache status enum.
- `http_status`: HTTP response status when a request was made.
- `etag`: last received HTTP `ETag` validator.
- `last_modified`: last received HTTP `Last-Modified` validator.
- `cache_control`: last received HTTP `Cache-Control` header.
- `fetched_at`: timestamp for the last successful body fetch.
- `validated_at`: timestamp for the last cache validation attempt.
- `expires_at`: optional future timestamp for explicit cache expiration.
- `content_sha256`: SHA-256 hash of the fetched body.
- `parsed_sha256`: SHA-256 hash of the normalized parsed record when available.
- `body_path`: local cached response body path.
- `asset_path`: local static asset path when the row represents an icon/image.
- `content_type`: fetched content type when known.
- `byte_length`: fetched body byte length.
- `warnings`: non-fatal warnings.
- `errors`: fetch or parse errors.

## Status Enum

- `fetched`: a new body was downloaded and cached.
- `fresh_cache`: the local cache entry was younger than the configured stale age and no network request was made.
- `not_modified`: AscensionDB returned `304 Not Modified`; the cached body was reused.
- `parse_failed`: the body was fetched but parser output could not be produced.
- `fetch_failed`: the request failed after retry policy.
- `asset_missing`: an icon/image URL could not be resolved.
- `skipped`: the row was skipped by CLI filters, limits, or depth controls.

## Refresh Rules

Default behavior:

1. If a row is younger than `--stale-days`, use `fresh_cache`.
2. If stale and `etag` exists, send `If-None-Match`.
3. If stale and `last_modified` exists, send `If-Modified-Since`.
4. If AscensionDB returns `304`, reuse the cached body and update `validated_at`.
5. If AscensionDB returns `200`, write the new body and update content metadata.
6. If no validators exist, use stale age plus content and parsed hashes to avoid rewriting unchanged artifacts.

Recommended public defaults:

- `--stale-days 7`
- `--concurrency 4`
- `--timeout-ms 10000`
- one retry for transient failures with jitter

## Hashing

`content_sha256` is computed over the exact response body text or binary content.

`parsed_sha256` is computed over a canonical JSON representation of the parsed record. It can be omitted until the parser stage attaches normalized rows.

