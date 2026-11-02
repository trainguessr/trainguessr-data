# Railway station datasets

This repository builds ready-to-use railway station datasets for several European countries and networks.

The generated files are in [`nodes/`](nodes/). Each file is newline-delimited JSON: one station per line. A station normally has:

```json
{"type":"node","id":"...","lat":0.0,"lon":0.0,"tags":{"name":"..."},"category":"..."}
```

`id` is the station ID used by the source or timetable provider. `category` is the provider namespace. Extra source fields are kept in `tags` when useful.

You can use the files directly.
## Quick start

Run commands from this repository root.

```bash
python3 -m gen.countries <country>
```

Italy uses one command for several providers:

```bash
python3 -m gen.countries italy generate all
python3 -m gen.countries italy generate rfi
python3 -m gen.countries italy review all
```

See [`docs/README.md`](docs/README.md) for the full country list and source notes.

## Repository layout

- `nodes/` — generated station datasets.
- `gen/countries/` — everyday country generators.
- `gen/common/` — shared download, output, and validation helpers.
- `gen/maintenance/` — dataset checks and file-age report.
- `gen/bootstrap/` — one-time research and reconstruction tools.
- `overrides/` — reviewed exclusions, renames, aliases, coordinates, and provider mappings.
- `docs/` — short country guides.
- `cache/` — downloaded source files, generated reports, and other disposable working data.
- `tests/` — data and generator tests.

## Safe generation

Generators check the new file before replacing a station file. They stop if it is empty or has an unexpected large drop. An unchanged file is not rewritten. All generators keep the existing station order; new stations are appended in source-ID order. Upstream row or JSON-key ordering alone does not rewrite a file. Italian generators stop for a review when a station ID, name, or coordinate needs a decision; see the Italy guide.

Use `--cache` to build from saved source files without downloading. The flag has the same meaning for every country generator. Some providers also accept local input files; see the country guide.

Reviewed decisions go into `overrides/`. Generated reports and downloaded files instead finish in the ignored `cache/` directory. One-time research evidence and tools can be found under `gen/bootstrap/`. If a provider reuses an ID or changes a station name, generation should ask for a review before using the saved decision.

## Validation

```bash
python3 gen/maintenance/validate_all.py
python3 -m pytest -q  # requires pytest installed in the active Python environment
git diff --check
```

The runtime `requirements.txt` intentionally does not include test tooling.
If the test command reports `No module named pytest`, activate the generator
virtual environment and install the development dependencies:
`python3 -m pip install -r requirements-dev.txt` (or `uv pip install -r
requirements-dev.txt` when using uv).

To see which datasets may need a refresh:

```bash
python3 gen/maintenance/freshness.py
```

## Sources and licences

See the [ODbL notice](LICENSE), [source attribution](ACKNOWLEDGMENTS.md),
[per-dataset rights status](docs/source-terms.json), and
[publication checklist](docs/publication.md). Not every upstream source is
cleared for arbitrary redistribution; generation success is not a rights grant.
Country-specific details are in [`docs/`](docs/).
