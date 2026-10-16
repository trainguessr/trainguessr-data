# Dataset guide

The files in `nodes/` are public railway station datasets built from provider and open-data sources.

Each station keeps the ID used by its source or timetable provider. Geographic sources such as OpenStreetMap can help check a place, but they do not replace a provider ID with a guessed one.

## Countries and datasets

| Country | Category | Nodes | Generator |
| --- | --- | ---: | --- |
| [Austria](austria.md) | `austria_oebb` | 1,416 | `python3 gen/austria.py` |
| [Belgium](belgium.md) | `belgium_all` | 604 | `python3 gen/belgium.py` |
| [Denmark](denmark.md) | `denmark_all` | 563 | `python3 gen/denmark.py` |
| [Finland](finland.md) | `finland_all` | 222 | `python3 gen/finland.py` |
| [France](france.md) | `france_sncf` | 2,854 | `python3 gen/france.py` |
| [Germany](germany.md) | `germany_all` | 6,652 | `python3 gen/germany.py` |
| [Italy](italy.md) | `italy_rfi` | 2,426 | `python3 gen/italy.py generate rfi` |
| [Italy](italy.md) | `italy_fn` | 111 | `python3 gen/italy.py generate fn` |
| [Italy](italy.md) | `italy_fse` | 92 | `python3 gen/italy.py generate fse` |
| [Italy](italy.md) | `italy_tt` | 38 | `python3 gen/italy.py generate tt` |
| [Italy](italy.md) | `italy_fer` | 117 | `python3 gen/italy.py generate fer` |
| [Italy](italy.md) | `italy_eav` | 119 | `python3 gen/italy.py generate eav` |
| [Italy](italy.md) | `italy_sta` | 17 | `python3 gen/italy.py generate sta --write-nodes` |
| [Netherlands](netherlands.md) | `netherlands_all` | 397 | `python3 gen/netherlands.py` |
| [Norway](norway.md) | `norway_all` | 367 | `python3 gen/norway.py` |
| [Spain](spain.md) | `spain_renfe`, `spain_fgc` | 1,457 + 91 | `python3 gen/spain.py` |
| [Sweden](sweden.md) | `sweden_all` | 832 | `python3 gen/sweden.py` |
| [Switzerland](switzerland.md) | `switzerland_all` | 1,697 | `python3 gen/switzerland.py` |
| [United Kingdom](uk.md) | `uk_national_rail` | 2,609 | `python3 gen/uk.py` |

Counts above match the committed files in `nodes/`.

## Updating a dataset

1. Run the country generator from the repository root.
2. Read its warnings and review report.
3. Check the diff in `nodes/` and `overrides/`.
4. Run the validation commands from the root README.

`cache/` is disposable. `overrides/` contains reviewed decisions that change output. `docs/review/` contains large evidence and audit files.

## Review rules

- Do not guess a provider ID from a station name, coordinates, route order, or a nearby ID.
- Keep enough source identity in reviewed changes to detect later upstream changes.
- If a source schema changes, fail clearly instead of silently skipping bad records.
- Keep large reconciliation records in `docs/review/`, not in the short country guides.

Italy has several datasets behind `gen/italy.py`; see [`italy.md`](italy.md). Finland, France, and Germany also have optional reconciliation tools described in their country pages.
