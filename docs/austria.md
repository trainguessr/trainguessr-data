# Austria

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Austria | `austria_oebb` | ÖBB SCOTTY | `gen/austria.py` using GeoNetz and MVO | 1,416 nodes; 55 physical provider gaps across 12 named systems are recorded in `docs/review/austria-dataset-coverage.json`. |

## Generation and source notes

Austria uses ÖBB SCOTTY for live boards. The station catalogue keeps the existing [ÖBB GeoNetz](https://data.oebb.at/de/datensaetze~geo-netz~) EVA IDs and fills private/regional rail gaps from the nationwide [MVO stop dataset](https://mobilitaetsdaten.gv.at/en/daten/%C3%B6sterreichweite-haltestellen). New MVO stops are accepted only when they resolve unambiguously to a SCOTTY station.

Run `python3 gen/austria.py` from the repository root to keep the GeoNetz catalogue and automatically add data from the official public MVO sample. Set `MVO_USERNAME` and `MVO_PASSWORD` to use the current authenticated production snapshot, or pass `--mvo-input` to use a reviewed MVO ZIP containing `haltestellen.csv` and `steige.csv`. Dataset scope and known limits are in `docs/review/austria-dataset-coverage.json`.

For a zero-network replay, use `python3 gen/austria.py --offline --mvo-input cache/austria/mvo-haltestellen.zip`. This requires `cache/austria/austria_stations_filtered.json` and `cache/austria/scotty-resolutions.json`. Uncached stops are unresolved. The run makes no GeoNetz, MVO, or SCOTTY requests and marks nodes with `scotty_board_status=offline_cached_resolution`. Normal runs use live SCOTTY verification.

`gen/austria.py` is the single Austria generator. It also owns the optional ÖBB GTFS operator-enrichment index. After downloading the official GTFS archive through ÖBB's terms-gated download, build just the runtime index with:

```bash
python3 gen/austria.py \
  --oebb-gtfs cache/austria/GTFS_Fahrplan_2026.zip \
  --oebb-operator-index-only
```

The generated operator index is version 2. It stores both exact GTFS `trip_short_name` values and official `route_short_name` line labels, plus the exact Austrian IFOPT represented by each stop. Runtime enrichment first attempts station + exact trip name + active service date. If SCOTTY exposes only a line label such as `S 3` or `REX 2`, it may use station + official route label + active service date only when all matching active trips have one agency. Cross-agency matches remain unresolved.

The same `--oebb-gtfs` flag may be supplied during a normal station generation run. Relevant flags are:

- `--mvo-input PATH`: reviewed/local MVO ZIP instead of downloading it.
- `--offline`: zero-network station rebuild from durable cached inputs.
- `--output PATH`: station node output.
- `--audit PATH`: station reconciliation audit output.
- `--oebb-gtfs PATH`: local official ÖBB GTFS ZIP; root GTFS, one wrapper directory, and one nested GTFS ZIP are accepted.
- `--oebb-operator-index PATH`: runtime SQLite output; defaults to `cache/austria-oebb-operators.sqlite`.
- `--oebb-operator-audit PATH`: durable index-build audit; defaults to `cache/austria/oebb-operator-index-audit.json`.
- `--oebb-operator-index-only`: skip station generation and build only the operator index; requires `--oebb-gtfs`.

Austria follows the repository cache policy: durable source material and audits live in `cache/austria/`, deployable runtime SQLite indexes may live directly in `cache/`, and disposable GeoNetz extraction is staged under `cache/temp/austria/` and removed after use. Older root-level Austria cache artifacts are moved into `cache/austria/` when encountered.


## Attribution and provider constraints

- Stations: ÖBB-Infrastruktur GeoNetz and the national MVO stop dataset.
- Live boards: ÖBB SCOTTY.
- Attribution: `Datenquelle: ÖBB-Infrastruktur AG` for GeoNetz data, under CC BY 3.0 Austria.
- Constraint: get authorization for public use of the consumer SCOTTY endpoint or move to an authorized API product.


## Other providers

The 55 physical provider gaps span 12 private/regional systems and are recorded in `docs/review/austria-dataset-coverage.json`.
