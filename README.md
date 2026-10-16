# Railway station datasets

This repository builds ready-to-use railway station datasets for several European countries and networks.

The generated files are in [`nodes/`](nodes/). Each file is newline-delimited JSON: one station per line. A station normally has:

```json
{"type":"node","id":"...","lat":0.0,"lon":0.0,"tags":{"name":"..."},"category":"..."}
```

`id` is the station ID used by the source or timetable provider. `category` is the provider namespace. Extra source fields are kept in `tags` when useful.

You can use the files directly. TrainGuessr is one consumer of this repository, but the data repository does not depend on the TrainGuessr application.

## Quick start

Run commands from this repository root.

```bash
python3 gen/<country>.py
```

Italy uses one command for several providers:

```bash
python3 gen/italy.py generate all
python3 gen/italy.py generate rfi
python3 gen/italy.py review all
```

See [`docs/README.md`](docs/README.md) for the full country list and source notes.

## Repository layout

- `nodes/` — generated station datasets.
- `gen/` — generators and review tools.
- `overrides/` — reviewed exclusions, renames, aliases, coordinates, and provider mappings.
- `docs/` — short country guides.
- `docs/review/` — large audit and reconciliation records.
- `cache/` — disposable downloaded or generated working data.
- `tests/` — data and generator tests.

## Safe generation

Generators validate output before replacing a station file. Empty output and unexpected large drops are rejected.

Use `--cache` only when you want to reuse downloaded input. Some generators also support `--offline` or local source files; see the country guide.

Reviewed decisions belong in `overrides/`. Large evidence files belong in `docs/review/`. If a source record changes identity, generation should stop for review instead of silently reusing an old decision.

## Validation

```bash
python3 gen/maintenance/validate_all.py
python3 -m pytest -q
git diff --check
```

To see which datasets may need a refresh:

```bash
python3 gen/maintenance/freshness.py
```

## Sources and licences

See [`ACKNOWLEDGMENTS.md`](ACKNOWLEDGMENTS.md) for source, licence, and attribution notes. Country-specific details are in [`docs/`](docs/).
