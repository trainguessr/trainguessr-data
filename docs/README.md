# Dataset guide

The files in `nodes/` are public railway station datasets built from provider and open-data sources.

Each station keeps the ID used by its source or timetable provider. Geographic sources such as OpenStreetMap can help check a place, but they do not replace a provider ID with a guessed one.

## Countries and datasets

| Country | Categories | Generator |
| --- | --- | --- |
| [Austria](austria.md) | `austria_oebb` | `python3 -m gen.countries austria` |
| [Belgium](belgium.md) | `belgium_all` | `python3 -m gen.countries belgium` |
| [Denmark](denmark.md) | `denmark_all` | `python3 -m gen.countries denmark` |
| [Finland](finland.md) | `finland_all` | `python3 -m gen.countries finland` |
| [France](france.md) | `france_sncf` | `python3 -m gen.countries france` |
| [Germany](germany.md) | `germany_all` | `python3 -m gen.countries germany` |
| [Italy](italy.md) | `italy_rfi`, `italy_fn`, `italy_fse`, `italy_tt`, `italy_fer`, `italy_eav`, `italy_sta` | `python3 -m gen.countries italy generate <provider>` |
| [Netherlands](netherlands.md) | `netherlands_all` | `python3 -m gen.countries netherlands` |
| [Norway](norway.md) | `norway_all` | `python3 -m gen.countries norway` |
| [Spain](spain.md) | `spain_renfe`, `spain_fgc` | `python3 -m gen.countries spain` |
| [Sweden](sweden.md) | `sweden_all` | `python3 -m gen.countries sweden` |
| [Switzerland](switzerland.md) | `switzerland_all` | `python3 -m gen.countries switzerland` |
| [United Kingdom](uk.md) | `uk_national_rail` | `python3 -m gen.countries uk` |

## Updating a dataset

1. Run the country generator from the repository root. A successful run exits
   zero. If the station file is already the same, it is left alone.
2. If the Italian generator finds a change that needs a decision, it asks in an
   interactive terminal. Without a terminal, it keeps the current station file,
   saves a report under `cache/`, and exits with an error. Review later with
   `python3 -m gen.countries italy review <provider>`.
3. Validate with the root README commands, then check actual Git changes.
   A zero exit status is not proof every source carries every passenger stop.

`cache/` contains disposable downloads and reports. `overrides/` contains reviewed decisions that change output. One-time research tools are in `gen/bootstrap/`.

## Review rules

- Do not guess a provider ID from a station name, coordinates, route order, or a nearby ID.
- Keep the provider ID and station name with each saved decision so later downloads can be checked.
- If a provider changes its file format, stop with a clear error instead of skipping records.
- Keep generated reports in `cache/`; keep reviewed decisions in `overrides/`.

Italy has several providers behind `python3 -m gen.countries italy`; see [`italy.md`](italy.md). One-time research tools are available through `python3 -m gen.bootstrap --help`.
