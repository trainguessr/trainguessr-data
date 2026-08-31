# Austria

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Austria | `austria_oebb` | ÖBB SCOTTY | `gen/austria.py` using GeoNetz and MVO | 1,416 nodes; 55 physical provider gaps across 12 named systems are recorded in `docs/review/austria-dataset-coverage.json`. |

## Generation and source notes

Austria uses ÖBB SCOTTY for live boards. The station catalogue keeps the existing [ÖBB GeoNetz](https://data.oebb.at/de/datensaetze~geo-netz~) EVA IDs and fills private/regional rail gaps from the nationwide [MVO stop dataset](https://mobilitaetsdaten.gv.at/en/daten/%C3%B6sterreichweite-haltestellen). New MVO stops are accepted only when they resolve unambiguously to a SCOTTY station.

Run `python3 gen/austria.py` from the repository root to keep the GeoNetz catalogue and automatically add data from the official public MVO sample. Set `MVO_USERNAME` and `MVO_PASSWORD` to use the current authenticated production snapshot, or pass `--mvo-input` to use a reviewed MVO ZIP containing `haltestellen.csv` and `steige.csv`. Dataset scope and known limits are in `docs/review/austria-dataset-coverage.json`.

For a zero-network replay, use `python3 gen/austria.py --offline --mvo-input cache/austria/mvo-haltestellen.zip`. This requires `cache/austria_stations_filtered.json` and `cache/austria/scotty-resolutions.json`. Uncached stops are unresolved. The run makes no GeoNetz, MVO, or SCOTTY requests and marks nodes with `scotty_board_status=offline_cached_resolution`. Normal runs use live SCOTTY verification.


## Attribution and provider constraints

- Stations: ÖBB-Infrastruktur GeoNetz and the national MVO stop dataset.
- Live boards: ÖBB SCOTTY.
- Attribution: `Datenquelle: ÖBB-Infrastruktur AG` for GeoNetz data, under CC BY 3.0 Austria.
- Constraint: get authorization for public use of the consumer SCOTTY endpoint or move to an authorized API product.


## Other providers

The 55 physical provider gaps span 12 private/regional systems and are recorded in `docs/review/austria-dataset-coverage.json` and summarized in `docs/new-providers.md`.
