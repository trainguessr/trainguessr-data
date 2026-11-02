# Germany

## Current providers

- **Category:** `germany_all`
- **Current nodes:** 6,652
- **Runtime:** Deutsche Bahn Timetables and bahnhof.de
- **Runtime ID:** DB EVA
- **Station source:** `db-stations`, plus reviewed additions

## Generate

```bash
python3 -m gen.countries germany
```

Use `--cache` to build from the saved `db-stations` files without downloading.

Reviewed board groups and mappings are in `../overrides/germany-board-groups.json` and `../overrides/germany-station-mappings.json`.

## Audit

```bash
python3 -m gen.bootstrap germany --help
```

The one-time research report is written under `cache/germany/`. Reviewed additions are in `../overrides/germany-stations.csv`. Keep DB IDs from DB sources; do not guess them from names, maps, or coordinates.

U-Bahn, tram, and separate heritage/private systems are outside this heavy-rail category unless they have a verified DB identity.

## Other providers

U-Bahn, tram, and separate heritage/private systems need their own provider unless they have a verified DB identity.

## Terms

DB open station data requires Deutsche Bahn attribution. The Timetables API needs an API subscription and its request limits must be respected. See `../ACKNOWLEDGMENTS.md`.
