# Dataset guide

Every station keeps the ID given by its railway or timetable provider. Maps like
OpenStreetMap can help check a place, but they never replace a real ID with a
guessed one.

## Countries

| Country | Categories | Command |
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

## Update a dataset

1. Run the command for the country. If nothing changed, the file stays the same.
2. Italy may find a change that needs a decision. In a terminal, it asks you.
   Without a terminal, it keeps the old file, saves a report in `cache/` and
   stops with an error. Answer later with
   `python3 -m gen.countries italy review <provider>`.
3. Run the checks from the [main README](../README.md) and look at the Git diff.
   A run without errors does not prove that every stop is there.

## Rules

- Never guess an ID from a name, a position, the route or a nearby ID.
- Save the ID and the name with every decision, so later downloads can be checked.
- If a source changes its format, stop with a clear error. Do not skip rows.
- Reports go in `cache/`. Decisions go in `overrides/`.
- Do not throw away a foreign station's ID. If it is not playable, put it in
  `lookup/`, with the source row that proves the link.

Before you publish data, read the [publication checklist](publication.md).

One-time research tools: `python3 -m gen.bootstrap --help`.
