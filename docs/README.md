# TrainGuessr data documentation

This is the canonical cross-country documentation for the station-data repository.
Country pages contain provider-specific sources, evidence, licensing, completeness,
review decisions, and country-specific maintenance notes. Transient implementation
status and the active roadmap belong in the parent-workspace `plan.md`, not here.

## Countries

- [Austria](austria.md)
- [Belgium](belgium.md)
- [Denmark](denmark.md)
- [Finland](finland.md)
- [France](france.md)
- [Germany](germany.md)
- [Italy](italy.md)
- [Netherlands](netherlands.md)
- [Norway](norway.md)
- [Spain](spain.md)
- [Sweden](sweden.md)
- [Switzerland](switzerland.md)
- [United Kingdom](uk.md)

## Provider inventory

| Country | Category | Runtime provider | Station/source generator | Coverage and gap status |
| --- | --- | --- | --- | --- |
| Austria | `austria_oebb` | ÖBB SCOTTY | `gen/austria.py` using GeoNetz and MVO | 1,416 nodes; `docs/review/austria-dataset-coverage.json` identifies 55 physical provider gaps across 12 named systems. |
| Belgium | `belgium_all` | iRail/NMBS-SNCB | `gen/belgium.py`; Infrabel cross-check | 603 nodes; no confirmed mainstream iRail omission. Twenty heritage stations require five named operator-specific providers; urban metro/tram is separate. |
| Denmark | `denmark_all` | Rejseplanen GTFS/API 2.0 | `gen/denmark.py` | 631 nodes, including 173 current Letbane stop IDs. Current provider/operator services are listed in `docs/denmark.md`; 44 metro stops are deferred to a later mode phase. |
| Finland | `finland_all` | Fintraffic Digitraffic | `gen/finland.py` and `docs/review/finland-reconciliation.json` | 222 nodes, including 13 no-current-traffic station sites. The audit has 262 official operational/non-passenger outcomes and 24 explicit unresolved possible-former-passenger sites; Helsinki metro/tram requires HSL or another separate provider. |
| France | `france_sncf` | SNCF API/Navitia-compatible station namespace | `gen/france.py`; `gen/france.py --audit` | 2,846 nodes from the current 2,782-record SNCF export, 52 exact current SNCF Reseau passenger supplements (including one corrected Fontanil UIC), nine exact-UIC historical passenger supplements, and six reviewed Cuneo-Ventimiglia supplements, after three explicit API-identity exclusions. The physical audit lists 20 deferred RATP/RER records, six separate-provider candidates, one Monaco scope gap, and seven unresolved SNCF/Occitanie candidates. Corsica CFC is a separate 65-stop `new_provider_needed` system. |
| Germany | `germany_all` | Deutsche Bahn Timetables/bahnhof boards | `gen/germany.py` and `docs/review/germany-reconciliation.json` | 6,652 nodes: 5,388 cached DB records, 33 AKN supplements, and 1,231 current-provider DB EVA additions. The audit lists 7 explicit current-provider gaps, 54 separate-system candidate records, and 40 stale catalogue IDs for lifecycle review; U-Bahn/tram is separate. |
| Italy | `italy_sta` | STA / südtirolmobil | `gen/italy.py generate sta --write-nodes` | 17 native Vinschgau nodes; exact STA IDs augment 29 shared RFI and 10 shared ÖBB nodes. |
| Italy | `italy_rfi` | Rete Ferroviaria Italiana / ViaggiaTreno | `gen/italy.py generate rfi` | 2,426 nodes from 2,438 source rows; six French cross-border boards use `france_sncf`, and six records are excluded. |
| Italy | `italy_fn` | Ferrovienord / Trenord | `gen/italy.py generate fn` | 111 nodes from 117 source rows; six explicit exclusions. |
| Italy | `italy_fse` | Ferrovie del Sud Est / ViaggiaTreno | `gen/italy.py generate fse` | 92 nodes from 95 source rows: 85 automatic matches, seven manual records including disused Gallipoli Porto, and three explicit non-FSE/duplicate exclusions. |
| Italy | `italy_tt` | Trentino Trasporti / legacy TrainView | `gen/italy.py generate tt` | 38 matched legacy records; runtime is disabled because the historical live endpoint is unavailable. |
| Italy | `italy_fer` | Ferrovie Emilia Romagna / PittiInfo | `gen/italy.py generate fer` | 119 nodes from 132 source rows; 13 explicit exclusions and guarded reviewed coordinates, including `S05100`. |
| Italy | `italy_eav` | Ente Autonomo Volturno | `gen/italy.py generate eav` | 119 nodes from 126 source rows; seven explicit exclusions. |
| Netherlands | `netherlands_all` | Rijden de Treinen / NS and other Dutch operators | `gen/netherlands.py` | 397 nodes. Rijden de Treinen describes its NL catalogue as all Dutch railway stations, sourced directly from NS and refreshed for station openings, closures, and renames. The data includes two `facultatiefStation` records. Metro/tram is separate. |
| Norway | `norway_all` | Entur Journey Planner / National Stop Register | `gen/norway.py` | 367 active rail nodes. Entur requires stops in use to be ACTIVE and publishes nightly current, future, and all-version/outdated NeTEx dumps with stable NSR IDs. The generator excludes INACTIVE records pending historical and physical review. Metro/tram is deferred. |
| Spain | `spain_renfe` | Renfe official GTFS and GTFS-Realtime | `gen/spain.py` | 1,465 tracked nodes. Explicit provider-native stations are included even when no current trip serves them. Renfe's complete-stations catalogue is an authoritative cross-check, but its CSV download is unavailable from the portal archiver. |
| Spain | `spain_fgc` | FGC official GTFS and GTFS-Realtime | `gen/spain.py --skip-renfe --fgc <feed> --no-download` | 91 rail nodes from the 2026-08-26 official feed; 14 rail routes and 6,526 rail trips. Metro, funicular, rack, and replacement-bus routes are deferred. |
| Sweden | `sweden_all` | Trafiklab ResRobot | `gen/sweden.py` | 839 nodes: 739 rail and 100 metro. Trafiklab’s national stop data/ResRobot covers all Swedish operators, uses the same national `740...` stop IDs as GTFS Sverige 2, and refreshes when source data changes. The generator has no current-trip gate. Ordinary tram expansion is out of scope; the existing provider covers metro. |
| Switzerland | `switzerland_all` | Search.ch stationboard / Swiss Transport API | `gen/switzerland.py` | 1,697 current `TRAIN` service-point nodes. Swiss service-point v2 also publishes full past/future validity records; the generator reads current service points and filters `meansoftransport=TRAIN`. Non-TRAIN and historical records need proof of a physical passenger station addressable by search.ch. |
| United Kingdom | `uk_national_rail` | National Rail Darwin, with Huxley2 fallback | `gen/uk.py` | 2,608 nodes. The upstream catalogue contains 2,608 stations queryable through National Rail Darwin, including Cambridge South (`CMS`) and Beaulieu Park (`BPA`). Northern Ireland Railways and heritage/private systems are future-provider entries; metro is deferred. |

## Repository maintenance and reproducibility

### Directory contract

`cache/` has files that can be downloaded or generated again and is ignored.
`nodes/` has the playable generated output.
`docs/` has guides plus machine-readable evidence and
reconciliation ledgers.
`gen/` has one public country entrypoint per supported country. Complex code is
under `gen/common/`, `gen/countries/`, or `gen/reconcile/`.
`overrides/` has only reviewed settings that change generated output.
`tests/` has committed regression tests.

### Public generator entrypoints

Run `python3 gen/<country>.py` for normal generation. For Finland, France, and
Germany, run `python3 gen/<country>.py --audit` for physical/provider
reconciliation.

Italy uses one dispatcher:

```bash
python3 gen/italy.py generate all
python3 gen/italy.py generate rfi
python3 gen/italy.py review all
python3 gen/italy.py rebuild all --dry-run
```

Provider-specific Italian code is under `gen/countries/italy/`.

### Reviewed decisions

Put exclusions, renames, coordinate corrections, aliases, and manually reviewed
provider mappings under `overrides/`. Each record must check station identity so
an upstream rename or ID change cannot silently apply an old decision to another
station.

Put large discovery and reconciliation results under `docs/review/`. Generators
may read reviewed source and evidence records there, but code must use only
explicit terminal statuses.

### Breaking upstream changes

Generators must validate required source fields and fail on incompatible schema
changes. A source refresh must not silently shrink the catalogue because a field
disappeared, an endpoint returned the wrong representation, or a timetable
window contained no service.

Stable TrainGuessr/provider identities must not change when upstream arrays are
reordered. Set canonical IDs and aliases explicitly.

### Fresh-clone expectation

A clean clone without `cache/` must:
1. import and compile all generators and tests;
2. validate all committed `nodes/`;
3. run the normal test suite without failures;
4. skip only tests that need a cache download, credentials, or opt-in live
   access.

Live rebuilds may need credentials or network access. The country page must list
the exact command, input, and blocker.

## Generator conventions

`gen/` has one **public launcher per country**. Run those launchers from the
`trainguessr-data` repository root:

```sh
python3 gen/italy.py --help
python3 gen/spain.py --help
python3 gen/germany.py
```

`gen/countries/` contains provider-specific implementation modules used by
those launchers. They are not a second set of country entrypoints. New
multi-provider countries should keep their public CLI at `gen/<country>.py`
and put provider-specific source/crawling logic under
`gen/countries/<country>/`.

`gen/common/` contains shared deterministic I/O, normalization, validation and
manual-review helpers. `gen/reconcile/` contains reconciliation/capture helpers
that are not normal generation entrypoints.

### Italy

Use the country launcher for normal work:

```sh
# Refresh the STA source cache and review reports; nodes are unchanged.
python3 gen/italy.py generate sta

# After review, write only Vinschgau STA nodes and augment shared RFI/ÖBB nodes.
python3 gen/italy.py generate sta --write-nodes

# Existing providers:
python3 gen/italy.py generate rfi
python3 gen/italy.py generate all
python3 gen/italy.py review all
python3 gen/italy.py rebuild all --dry-run
```

For debugging only, provider modules may expose their own CLI. STA deliberately
supports direct execution too:

```sh
python3 gen/countries/italy/sta.py
python3 gen/countries/italy/sta.py --write-nodes
```

Both STA forms have identical semantics. The default is non-destructive.
