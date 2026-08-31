# Spain

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Spain | `spain_renfe` | Renfe official GTFS and GTFS-Realtime | `gen/spain.py` | 1,465 tracked nodes. Explicit provider-native stations are included even when no current trip serves them. Renfe's complete-stations catalogue is an authoritative cross-check, but its CSV download is unavailable from the portal archiver. |
| Spain | `spain_fgc` | FGC official GTFS and GTFS-Realtime | `gen/spain.py --skip-renfe --fgc <feed> --no-download` | 91 FGC rail nodes from the 2026-08-26 official feed. Metro, funicular, rack, and replacement-bus routes are outside this first pass. |

## Generation and source notes

Spain uses official Renfe and FGC GTFS archives. Run the Renfe generator from the
repository root:

```bash
python3 gen/spain.py
```

The generator downloads current Renfe archives into `cache/spain/`, then writes
`nodes/nodes-spain-renfe.json` and `cache/spain.sqlite`. Use `--cercanias`,
`--long-distance`, and `--no-download` to rebuild from local archives.

Downloaded GTFS archives are ignored by Git. Deploy
`cache/spain.sqlite` alongside the `nodes/` directory in the data volume. When
production uses `DATA_DIR=/data/nodes` and `DATA_CACHE_DIR=/data/cache`, the
application reads `/data/cache/spain.sqlite`. Exact source URLs and attribution
requirements are recorded below.


## Detailed review notes

Static source: official Renfe Data GTFS archives for Cercanías/Rodalies and high-speed/long-/medium-distance services.

Dataset pages and current archive URLs:

- <https://data.renfe.com/dataset/horarios-cercanias>
- <https://data.renfe.com/dataset/horarios-de-alta-velocidad-larga-distancia-y-media-distancia>
- <https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip>
- <https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip>

Runtime source: official Renfe GTFS-Realtime trip updates (`trip_updates.json` and `trip_updates_LD.json`).

Trips are namespaced by feed (`cercanias:` or `ld:`), while shared physical stations use their stable Renfe stop code and are merged across both feeds.

Catalogue membership is not identical to the current trip set. An
explicit GTFS station (`location_type=1`) is included even when no rail trip in
the downloaded timetable currently serves it. This prevents a temporary
service interruption from deleting a provider-native Renfe station. Child
stops and unparented bus/replacement stops are still not promoted merely
because they occur in the mixed Cercanías feed.

Renfe also publishes the CC BY 4.0 `Estaciones. Listado completo` catalogue
(<https://data.renfe.com/dataset/estaciones-listado-completo>), described as all
stations where Renfe operates and including Cercanías, FEVE/Ancho Métrico,
long-distance and medium-distance fields. As of 2026-08-30 the portal metadata
is current, but its direct CSV archiver reports a persistent SSL download
failure. Use it as the authoritative completeness cross-check when accessible;
do not fabricate station IDs when it is unavailable.

The application opens the normalized index read-only and queries the requested
station instead of loading the national schedule into memory.

Renfe publishes portal-specific public-sector reuse terms, not a CC BY
declaration. Include `Origen de los datos: Renfe Operadora`, source
and update metadata where supplied, and do not imply Renfe endorsement.

## Attribution and provider constraints

- Stations and static timetables: official Renfe GTFS feeds.
- Live updates: official Renfe GTFS-Realtime trip updates.
- Attribution: `Origen de los datos: Renfe Operadora`, with source and update metadata required by the portal reuse terms.
- Constraint: do not imply Renfe endorsement and review the portal terms before public publication.


## Other providers

Euskotren and other non-Renfe regional rail are outside the current scope. They
require their own provider namespace; do not assign them Renfe IDs.

See [`new-providers.md`](new-providers.md) for sources and next steps.


## FGC (`spain_fgc`)

FGC is a separate provider namespace from Renfe. The generator is
`gen/spain.py`; provider-specific implementation lives under
`gen/countries/spain/fgc.py`.

Sources:
- official FGC GTFS: `https://www.fgc.cat/google/google_transit.zip`;
- official FGC Open Data portal: `https://dadesobertes.fgc.cat/`;
- GTFS-Realtime Trip Updates dataset identifier: `trip-updates-gtfs_realtime`;
- GTFS-Realtime Service Alerts dataset identifier: `alerts-gtfs_realtime`;
- license: CC BY 4.0 on the FGC open-data catalogue;
- feed hash: `f247e1cb64134416608fe1b7a8510b4f7363a4b8e27b16e3a50dbd495e6fb1f7`;
- output: 91 rail stations from 14 rail routes and 6,526 rail trips.

The runtime reads Trip Updates. FGC lists Service Alerts as an official dataset,
but the adapter does not show them.

The first-pass scope is GTFS rail (`route_type=2` and extended rail types
100-199). Metro, bus, funicular, rack, and replacement-bus routes are outside it.
Playable IDs are copied from official FGC `stop_id` values. Child platforms are
collapsed only when the same feed supplies `parent_station`.

Run only FGC with a local official feed:

    python3 gen/spain.py --skip-renfe --fgc /path/to/google_transit.zip --no-download

Without `--fgc`, the generator downloads the file from FGC. The
runtime index is `cache/spain-fgc.sqlite`. Deploy it beside the node data. The
runtime rejects an expired static feed.

To capture Catalonia station, halt, and disused-site evidence, run:

```bash
PYTHONPATH=gen python3 gen/reconcile/spain_fgc_capture.py
```

The capture is ignored cache evidence and does not assign FGC IDs to OSM sites.
The 2026-08-31 capture matched all 91 generated stations within 198 metres.
