# coa_client_extract

Extraction-time-only capture of the local Ascension CoA client (M1.14A). Reads MPQ→DBC and loose
`Data/Content/*.json` into versioned artifacts. Never imported by `coa_meta`.

## Regenerate

    python -m coa_client_extract regenerate \
      --client-root "$HOME/Games/ascension-wow/drive_c/Program Files/Ascension Launcher/resources/ascension-live/Data" \
      --out reports/client_extract

Requires StormLib (MIT). Without it the command fails closed and writes nothing.

## Test tiers

- Default (`python -m pytest`): fake backend + synthetic fixtures. No StormLib, no client.
- `python -m pytest -m stormlib`: native StormLib patch-chain integration (miniature MPQs).
- `python -m pytest -m client`: acceptance against the real install (`COA_CLIENT_ROOT` overrides path).
