# Spain

## Current providers

Spain currently has two datasets.

| Category | Provider | Nodes | Output |
| --- | --- | ---: | --- |
| `spain_renfe` | Renfe GTFS / GTFS-Realtime | 1,461 | `nodes/nodes-spain-renfe.json` |
| `spain_fgc` | FGC GTFS / GTFS-Realtime | 91 | `nodes/nodes-spain-fgc.json` |

## Generate

```bash
python3 -m gen.countries spain
```

By default the generator downloads the current official static feeds and rebuilds the station files plus `cache/spain.sqlite`, which can also be used for timetable lookups.

Useful options:

```bash
python3 -m gen.countries spain --cache
python3 -m gen.countries spain --skip-fgc
python3 -m gen.countries spain --skip-renfe
python3 -m gen.countries spain --cercanias path/to.zip --long-distance path/to.zip --fgc path/to.zip --no-download
```

Renfe station IDs come from the official feeds. FGC IDs also come from its own official feed. Duplicate names, aliases, coordinate fixes, and exclusions are reviewed explicitly in `trainguessr-data/overrides/`.

Main review files:

- `trainguessr-data/overrides/exclusions/spain.json`
- `trainguessr-data/overrides/spain-reviewed-duplicate-names.json`
- `trainguessr-data/overrides/spain-station-corrections.csv`

Metro, funicular, rack, replacement-bus, heritage, and other non-current categories are not silently promoted into the two railway datasets.

## Other providers

Metro, funicular, rack, replacement-bus, and heritage systems are outside the two current railway datasets.

## Terms

Renfe and FGC feeds remain subject to their publishers' terms. Keep any required source attribution. See `../ACKNOWLEDGMENTS.md`.
