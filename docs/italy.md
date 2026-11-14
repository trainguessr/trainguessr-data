# Italy

## Current providers

Italy has several railway providers. They share one generator command: `python3 -m gen.countries italy`.

| Category | Provider | Command |
| --- | --- | --- |
| `italy_rfi` | RFI / ViaggiaTreno | `python3 -m gen.countries italy generate rfi` |
| `italy_fn` | Ferrovienord / Trenord | `python3 -m gen.countries italy generate fn` |
| `italy_fse` | Ferrovie del Sud Est / ViaggiaTreno | `python3 -m gen.countries italy generate fse` |
| `italy_tt` | Trentino Trasporti | `python3 -m gen.countries italy generate tt` |
| `italy_fer` | Ferrovie Emilia Romagna | `python3 -m gen.countries italy generate fer` |
| `italy_eav` | Ente Autonomo Volturno | `python3 -m gen.countries italy generate eav` |
| `italy_sta` | südtirolmobil / STA | `python3 -m gen.countries italy generate sta` |

## Generate and review

Generate one provider or all providers:

```bash
python3 -m gen.countries italy generate rfi
python3 -m gen.countries italy generate all
python3 -m gen.countries italy generate all --cache
```

Review saved changes without downloading again:

```bash
python3 -m gen.countries italy review all
python3 -m gen.countries italy review rfi
```

Check a rebuild without changing `nodes/`:

```bash
python3 -m gen.countries italy rebuild all --dry-run
```

In a terminal, generation opens a short review when new decisions are needed.
Without a terminal, it keeps the current station file, writes a report under
`cache/`, and exits with a clear message. Review later with the `review`
command above, then generate again.
For FSE, enter the exact ViaggiaTreno ID when the source name has no ID; an
OpenStreetMap ID is never used as the provider ID.

The current station file is the starting point for these providers. The generators check downloaded records against it. New IDs and changed names wait for review; a saved source file can be used with `--cache`.

STA checks its Vinschgau station list before writing. `--audit-only` writes a report without changing the station file. `--verbose` shows each StopFinder match and any optional ID matches. A missing optional ID does not remove a station.

Italian station exclusions, reasons, and source links are in `trainguessr-data/overrides/exclusions/italy.csv`. Its `evidence_ref` column points to the full station records in `trainguessr-data/gen/bootstrap/evidence/italy-exclusion-station-evidence.json`. Review choices are in `trainguessr-data/overrides/italy-decisions.csv`. Coordinate fixes are in `trainguessr-data/overrides/italy-coordinate-corrections.csv`. UIC station mappings are in `trainguessr-data/overrides/italy-uic-crosswalks.csv`; their source notes are in `trainguessr-data/gen/bootstrap/evidence/italy-uic-crosswalk-provenance.json`.

The RFI report lists new, changed, and missing source records. If an old station is missing from a download, it stays in the station file until a reviewer chooses what to do. Ponte San Cono (RFI ID 2221) is an existing reviewed exclusion because it is absent from the current RFI station list. A changed name such as GIACHERY PES needs a review.

## Important provider notes

- **RFI:** uses reviewed RFI station records. ViaggiaTreno `Sxxxxx` IDs are checked separately. They are never worked out from an RFI ID, route order, station name, or nearby station.
- **STA:** keeps the provider's Vinschgau station records and coordinates.
  `--audit-only` writes a report without publishing. `--verbose` shows extra
  IDs found through StopFinder. A station stays in the file when an extra ID
  is missing. Never invent an ID from a station name or location.
- **TT:** keeps legacy provider IDs, and its old live endpoint is no longer relied on by this data build.
- **FSE:** uses ViaggiaTreno IDs and reviewed physical station data. Shared RFI-managed stations stay in the RFI dataset.
- **FER, EAV, FN:** use reviewed provider records and stop when a station ID or name needs review.

The RFI/ViaggiaTreno review tool is:

```bash
python3 -m gen.bootstrap italy-viaggiatreno
```

Temporary research deferrals are stored in `trainguessr-data/overrides/italy-rfi-viaggiatreno-deferred.json`. This tool is for initial research; everyday station generation uses the commands above.

## Other providers

Several smaller Italian railways still need separate providers. Do not assign them an RFI/ViaggiaTreno identity without provider evidence.

## Terms

Many Italian live sources are consumer or undocumented endpoints. Public use may need written permission. Keep OSM/ODbL obligations where used. See `../ACKNOWLEDGMENTS.md`.

FN keeps its reviewed stations. New Trenord entries are shown for review only when their names match OSM railway stations owned by Ferrovienord (`operator=Ferrovienord` or `FN`, or `operator:wikidata=Q3736799`). This is a candidate filter, not proof of a provider ID. Unrelated entries are left out. OSM never replaces Trenord IDs or removes reviewed stations. `--cache` also needs the saved `cache/italy/fn/raw/ferrovienord-osm.json` source.

FSE reports real pending records in `cache/italy/fse/reports/unresolved.json` and already-excluded records in `excluded.json`. The summary prints both counts. Potenza S. Maria is FAL, Maglie Via Otranto is a bus stop, and the Sorbolo record is handled by FER; these are not forgotten FSE stations.

TT checks native station IDs against TrainView. GTFS labels are a separate comparison: a different GTFS label does not mean a native station ID is missing. The provider uses labels such as Gardolo-Ferrovia and Cles Ferrovia in GTFS. Existing reviewed display names are kept.

Missing RFI-to-ViaggiaTreno mappings are recorded in `overrides/italy-rfi-viaggiatreno-deferred.json`. These are mapping limits, not exclusions from the RFI station dataset. Some have no passenger service; others lacked exact VT evidence when checked. Roma Nomentana LM is freight-only, so no passenger VT ID is expected.


The shared train service also has seven finite reviewed RFI/SBB stop pairs for
the EC46 corridor. Their independent RFI page/place IDs, station-register UICs
and source limitations are recorded in the existing
`gen/bootstrap/evidence/italy-uic-crosswalk-provenance.json` review record.
They do not rewrite generated UIC tags: Verona's SBB and older HAFAS aliases
remain distinct source identifiers. Runtime joins use exact reviewed IDs, not
station spelling or UIC suffix arithmetic.

## Exact cross-provider station identifiers

RFI generation also downloads Trainline EU's `stations.csv` into
`cache/italy/rfi/raw/trainline-stations.csv`, with a checksum/revision sidecar.
`--cache` reuses that exact snapshot. Rebuilds apply it when present; absent raw
evidence leaves the reviewed seed metadata intact. Runtime never downloads it.
Only an existing reviewed `viaggiatreno_station_id` can select a unique Italian
non-city/non-alias record. Duplicate VT IDs, reused foreign identifiers and
invalid IDs are excluded. Names/coordinates do not select records.

Generated tags preserve the explicit `oebb_station_id`, `db_station_id`,
`trainline_uic_ref`, `trainline_station_id` and `station_identity_source`. Existing
reviewed `uic_ref` aliases stay intact; a missing UIC can be filled from the
explicit source field. Changed explicit foreign IDs require review. The train
service uses these catalogue IDs for dated occurrence joins, keeping station
identity separate from provider-local times/platforms and from train numbers.
Source: https://github.com/trainline-eu/stations, ODbL1.0.


## Known STA identity-provenance gaps

Chiusa native EFA66001051 (gid it:22021:1051) and Campo di Trens66001492
(gid it:22021:1492) have explicit current official sta-time-tables GTFS platform/
parent relationships. The GTFS source exposes no stop_code/UIC/IBNR or external
railway-equivalence metadata for them. It does not prove the ÖBB8300078/8300534
pairs. Existing name-selected catalogue aliases66000455/66002612 are not proof
for these railway stops. Preserve the native identities without guessing a bridge.

Official source: https://gtfs.api.opendatahub.com/v1/dataset/sta-time-tables/raw .
