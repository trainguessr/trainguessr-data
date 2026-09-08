# TrainGuessr railway stations dataset

This repository contains a dataset of geolocated railway stations across various European countries, along with scripts to generate and update the data.

## Repository layout

- `nodes/`: generated `ndjson` datasets.
- `cache/`: ignored source archives that can be downloaded again, plus generated runtime files.
- `docs/`: country and provider guides, reconciliation
  ledgers, current gaps, and maintenance notes.
- `gen/`: entrypoints for each supported country and lower-level shared/country modules.
- `overrides/`: reviewed settings that change generation behaviour, including exclusions, renames, aliases, coordinate corrections, and reviewed provider mappings.
- `tests/` — regression and data-integrity tests.

## Country documentation

See [`docs/README.md`](docs/README.md). Each country page lists:
- current providers for the country;
- sources and commands;
- override files;
- current status;
- source licence/attribution constraints;
- gaps outside the current scope.


## Generating data

Run generators from the repository root:

```bash
python3 gen/<country>.py
```

For countries with a physical/provider reconciliation mode, use the same
country entrypoint with `--audit`. See each relevant documentation page for required inputs and
credentials.

Italian providers use a single script:

```bash
python3 gen/italy.py generate all
python3 gen/italy.py generate rfi
python3 gen/italy.py review all
python3 gen/italy.py rebuild all --dry-run
```

Cache layout is intentional:

- `cache/*.sqlite`: deployable runtime indexes consumed by TrainGuessr services.
- `cache/<country>/`: durable, reproducible source downloads, reviewed resolution state, and audit outputs.
- `cache/temp/<country>/`: disposable extraction trees and intermediate files; generators should remove these after use.

Country-specific archives and snapshots must not be created at the cache root. Existing legacy root files may be adopted into their country directory by the relevant generator.

## Validation

From the repository root:

```bash
python3 gen/validate_all.py
python3 -m unittest discover -s tests -v
```

Also run:

```bash
git diff --check
python3 -m compileall -q gen tests
```

## Contribution rules

TrainGuessr station identity uses the timetable provider's native namespace.
OpenStreetMap/OpenRailwayMap can show that a physical station exists;
the runtime provider ID must be fetched from the provider's API or timetable data.

Stations are so far excluded only when they are physically demolished, i.e.,
a station that has seen no train stop in 20 years but remains open for routing purposes
is still included.

Exceptions must be machine-readable and contain a small description. 

When an upstream API/schema changes, generation should fail and throw errors.

See the relevant `docs/<country>.md` before changing a country's nodes.

## License and attribution

The generated station database is distributed under the repository's ODbL
licence, subject to source-specific terms. See
[`ACKNOWLEDGMENTS.md`](ACKNOWLEDGMENTS.md) for source/provider attribution and
`docs/` for country details.
