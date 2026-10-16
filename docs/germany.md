# Germany

## Current providers

- **Category:** `germany_all`
- **Current nodes:** 6,652
- **Runtime:** Deutsche Bahn Timetables and bahnhof.de
- **Runtime ID:** DB EVA
- **Station source:** `db-stations`, plus reviewed additions

## Generate

```bash
python3 gen/germany.py
```

Use `--cache` to reuse the local `db-stations` source instead of downloading it again.

Reviewed board groups and mappings are in `../overrides/germany-board-groups.json` and `../overrides/germany-station-mappings.json`.

## Audit

```bash
python3 gen/germany.py --audit --help
```

The reconciliation uses official DB identity checks plus rail/physical evidence. Its full output is in [`review/germany-reconciliation.json`](review/germany-reconciliation.json). Do not replace a DB EVA with a guessed ID from GTFS, OpenStreetMap, name similarity, or coordinates.

U-Bahn, tram, and separate heritage/private systems are outside this heavy-rail category unless they have a verified DB identity.

## Other providers

U-Bahn, tram, and separate heritage/private systems need their own provider unless they have a verified DB identity.

## Terms

DB open station data requires Deutsche Bahn attribution. The Timetables API needs an API subscription and its request limits must be respected. See `../ACKNOWLEDGMENTS.md`.
