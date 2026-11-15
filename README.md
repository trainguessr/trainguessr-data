# Railway station datasets

Ready-to-use railway station lists for many European countries.

The files are in [`nodes/`](nodes). Each line is one station, in JSON:

```json
{"type":"node","id":"...","lat":0.0,"lon":0.0,"tags":{"name":"..."},"category":"..."}
```

- `id` is the station ID used by the railway or timetable provider.
- `category` says which provider the station belongs to.
- `tags` holds the name and other useful source fields.

You can use the files as they are.

The files in [`lookup/`](lookup) use the same format, but their stations are not
playable. They are foreign stations that a provider knows by its own ID (for
example, DB's ID for Salzburg). They let a train be followed across a border.

## Build a dataset

Run commands from this folder.

```bash
python3 -m gen.countries <country>
```

Italy has several providers, so it has its own commands:

```bash
python3 -m gen.countries italy generate all
python3 -m gen.countries italy generate rfi
python3 -m gen.countries italy review all
```

Add `--cache` to build from files you already downloaded.

To rebuild the lookup files (after Italy RFI, which downloads the Trainline list):

```bash
python3 -m gen.countries lookup
```

The full country list is in the [dataset guide](docs/README.md).

## Safe by design

A generator never breaks a good file:

- It stops if the new file is empty or suddenly much smaller.
- It does not rewrite a file that did not change.
- Old stations keep their order. New stations go at the end.
- Italian generators stop and ask you when an ID, name or position changes.

## Folders

- `nodes/` — the station files.
- `lookup/` — not playable, only for linking IDs.
- `gen/countries/` — one generator per country.
- `gen/common/` — shared helpers.
- `gen/maintenance/` — checks and a freshness report.
- `gen/bootstrap/` — one-time research tools.
- `overrides/` — decisions made by hand (renames, exclusions, fixes).
- `docs/` — dataset guide, country guides and source rights.
- `cache/` — downloads and reports. Safe to delete.
- `tests/` — tests.

## Check your work

```bash
python3 -m pip install -r requirements-dev.txt   # once, for pytest
python3 gen/maintenance/validate_all.py
python3 -m pytest -q
git diff --check
```

To see which datasets are old:

```bash
python3 gen/maintenance/freshness.py
```

## Sources and licences

The datasets use the [ODbL licence](LICENSE). Sources are listed in
[ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md), and the rights of each dataset are in
[`docs/source-terms.json`](docs/source-terms.json).
Before publishing, follow the [publication checklist](docs/publication.md).

Careful: not every source allows free sharing. A file that builds is not a file
you may publish.
