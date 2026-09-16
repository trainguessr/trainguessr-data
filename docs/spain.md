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

Known non-Renfe provider gaps are summarized in [`provider-inventory.md`](README.md).


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


## Guarded coordinate corrections

- `23021` Padrón Barbanza
  - corrected to 42.7812443, -8.656552
  - evidence: current official Renfe station-data export
- `05403` Tremañes-Langreo
  - corrected to 43.527123, -5.690694
  - evidence: current official Renfe FEVE station list

The Renfe source also includes service/feed identities that are not distinct
physical passenger stations. The static timetable index includes them for trip
matching, but they are not separate playable nodes:

- `99117` Ourense Turístico -> `22100` Ourense
- `99161` Pontevedra-Turístico -> `23004` Pontevedra
- `99159` Santiago-Turístico -> `31400` Santiago de Compostela-Daniel Castelao
- `70001` Vallecas -> `70005` Vallecas

The alias mapping checks both provider ID and expected names. A source rename or
new identifier makes production generation fail so it can be reviewed.

## Heritage and low-service policy

Do not exclude a station only because it has sparse, seasonal, museum-only, or
no current timetable traffic. Keep it if it is part of an existing railway in
use. Its live timetable may be empty.


## FGC reconciliation evidence

### Sources

- Static timetable: [FGC Google Transit feed](https://www.fgc.cat/google/google_transit.zip)
- FGC open data: <https://dadesobertes.fgc.cat/>
- Physical evidence: `cache/spain/fgc/audit/osm-passenger-sites.json`
- Physical capture: `gen/reconcile/spain_fgc_capture.py`
- Feed SHA-256: `f247e1cb64134416608fe1b7a8510b4f7363a4b8e27b16e3a50dbd495e6fb1f7`

### Scope

The first pass includes GTFS rail routes (`route_type=2` and `100-199`). It
covers the Barcelona-Valles, Llobregat-Anoia, and Lleida-La Pobla services.
Metro, funicular, rack railway, and replacement bus routes are deferred.

The feed contains 305 stops, 22 routes, and 20,117 trips. Fourteen routes are
rail routes; eight routes are deferred.

### Generation

```bash
python gen/spain.py --skip-renfe --fgc /path/to/google_transit.zip --no-download
```

Outputs:

- `nodes/nodes-spain-fgc.json`: 91 stations
- `cache/spain-fgc.sqlite`: 6,526 rail trips
- 170 child stop IDs, each with `parent_station` set to its FGC station ID
- 0 stations without a rail trip

The generator copies station IDs, names, coordinates, route IDs, and child stop
IDs from the official feed. OSM data is used for physical corroboration only.

### Physical Evidence

Capture command:

```bash
PYTHONPATH=gen python gen/reconcile/spain_fgc_capture.py
```

The capture contains 1,453 Catalonia railway sites. Each of the 91 generated
stations matches a captured railway feature within 198 metres. Distances below
are rounded; OSM IDs and tags are kept in the capture file.

Query:

```text
[out:json][timeout:180];
area["ISO3166-2"="ES-CT"][boundary=administrative]->.a;
(
 nwr(area.a)["railway"~"^(station|halt|stop)$"];
 nwr(area.a)["disused:railway"~"^(station|halt|stop)$"];
 nwr(area.a)["abandoned:railway"~"^(station|halt|stop)$"];
);
out center tags;
```

### Terminal Ledger

`Rail trips` is the number of distinct official rail trips containing the
station. Every row has a current feed trip and a physical OSM match.

| FGC ID | Station | Rail routes | Child stop IDs | Rail trips | OSM evidence | Distance (m) | Decision |
| --- | --- | --- | --- | ---: | --- | ---: | --- |
| `AB` | Abrera | R5, R50, R53, S4 | AB1, AB2 | 590 | node/7515916374, Abrera | 4 | `playable` |
| `AE` | Montserrat-Aeri | R5, R53 | AE1 | 323 | node/1680233321, Aeri de Montserrat | 3 | `playable` |
| `AL` | Almeda | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | AL1, AL2 | 1489 | node/3398923274, Almeda | 61 | `playable` |
| `AR` | Àger | RL2 | AR1 | 30 | node/1834393194, Àger | 5 | `playable` |
| `AT` | Alcoletge | RL1, RL2 | AT1 | 86 | node/3954381914, Alcoletge | 78 | `playable` |
| `BE` | La Beguda | R6, R63 | BE1 | 332 | node/5418171757, la Beguda | 9 | `playable` |
| `BG` | Balaguer | RL1, RL2 | BG1, BG2 | 86 | node/3954388458, Balaguer | 6 | `playable` |
| `BN` | La Bonanova | S1, S2 | BN1, BN2 | 4904 | node/259649936, La Bonanova | 23 | `playable` |
| `BO` | Sant Boi | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | BO1, BO2 | 1489 | node/7515916367, Sant Boi | 11 | `playable` |
| `BT` | Bellaterra | S2 | BT1, BT2 | 2461 | node/9767567866, Bellaterra | 3 | `playable` |
| `CA` | Capellades | R6, R60, R63 | CA1, CA2 | 344 | node/9899950741, Capellades | 19 | `playable` |
| `CB` | Castellbell i El Vilar | R5, R53 | CB1 | 323 | node/7515916377, Castellbell i el Vilar | 3 | `playable` |
| `CF` | Can Feu - Gràcia | S2 | CF1, CF2 | 2461 | node/4380799243, Can Feu / Gràcia | 12 | `playable` |
| `CG` | Colònia Güell | R53, R63, S3, S4, S8, S9 | CG1, CG2 | 877 | node/7515916368, Colònia Güell | 33 | `playable` |
| `CL` | Santa Coloma de Cervelló | R53, R6, R60, R63, S3, S4, S8, S9 | CL1, CL2 | 1181 | node/370403889, Santa Coloma de Cervelló | 2 | `playable` |
| `CO` | Cornellà Riera | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | CO1, CO2 | 1489 | node/5315505600, Cornellà-Riera | 50 | `playable` |
| `CP` | Can Parellada | R6, R63 | CP1 | 332 | way/288492040, Can Parellada | 4 | `playable` |
| `CR` | Can Ros | R5, R53, R6, R63, S3, S4, S8, S9 | CR1, CR2 | 1465 | node/1966626240, Can Ros | 67 | `playable` |
| `CT` | La Creu Alta | S2 | CT1, CT2 | 2461 | node/4380799234, La Creu Alta | 9 | `playable` |
| `EN` | Terrassa  Estació del nord | S1 | EN1, EN2 | 2443 | node/7512362038, Terrassa Estació del Nord | 55 | `playable` |
| `EU` | Europa \| Fira | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | EU1, EU2 | 1489 | node/5331527851, Europa / Fira | 99 | `playable` |
| `FN` | Les Fonts | S1 | FN1, FN2 | 2443 | node/9757864303, Les Fonts | 28 | `playable` |
| `GB` | Gerb | RL2 | GB1 | 30 | node/4973648698, Gerb | 2 | `playable` |
| `GO` | Gornal | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | GO1, GO2 | 1489 | node/463272139, Gornal | 29 | `playable` |
| `GR` | Gràcia | S1, S2 | GR1, GR2 | 4904 | node/802777749, Gràcia | 19 | `playable` |
| `GT` | Guardia de Tremp | RL2 | GT1 | 30 | node/4774251842, Guàrdia de Tremp | 2 | `playable` |
| `HG` | Hospital General | S1 | HG1, HG2 | 2443 | node/9757864302, Hospital General | 7 | `playable` |
| `IC` | Ildefons Cerdà | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | IC1, IC2 | 1489 | node/3398928315, Ildefons Cerdà | 24 | `playable` |
| `IG` | Igualada | R6, R60, R63 | IG1, IG2 | 344 | node/13670468509, Igualada | 13 | `playable` |
| `LE` | Lleida | RL1, RL2 | LE1, LE2 | 86 | node/7487337013, Lleida-Pirineus | 88 | `playable` |
| `LF` | La Floresta | S1, S2 | LF1, LF2 | 4904 | node/9757864308, La Floresta | 3 | `playable` |
| `LH` | L'Hospitalet Av. Carrilet | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | LH1, LH2, LH3, LH4 | 1489 | node/463164973, Avinguda Carrilet | 16 | `playable` |
| `LL` | Cellers-Llimiana | RL2 | LL1 | 30 | node/1905681795, Cellers-Llimiana | 6 | `playable` |
| `LP` | Les Planes | S1, S2 | LP1, LP2 | 4904 | node/9757864309, Les Planes | 11 | `playable` |
| `LS` | Vilanova de la Sal | RL2 | LS1 | 30 | way/188616447, Vilanova de la Sal | 9 | `playable` |
| `MA` | Manresa-Alta | R5, R50, R53 | MA1, MA2 | 335 | node/7515916378, Manresa Alta | 4 | `playable` |
| `MB` | Manresa-Baixador | R5, R50, R53 | MB1, MB2 | 335 | node/3898960587, Manresa Baixador | 1 | `playable` |
| `MC` | Martorell Central | R5, R50, R53, R6, R60, R63, S4, S8 | MC1, MC2 | 1232 | node/7204816588, Martorell - Central | 36 | `playable` |
| `ME` | Martorell Enllaç | R5, R53, R6, R60, R63, S4, S8 | ME1, ME2 | 1232 | node/7204814143, Martorell Enllaç | 9 | `playable` |
| `MG` | Magòria La Campana | R5, R53, R6, R63, S3, S4, S8, S9 | MG1, MG2 | 1465 | node/3398928321, Magòria-La Campana | 5 | `playable` |
| `ML` | Molí Nou - Ciutat Cooperativa | R5, R53, R6, R63, S3, S4, S8, S9 | ML1, ML2 | 1465 | node/5264057233, Molí Nou / Ciutat Cooperativa | 1 | `playable` |
| `MN` | Muntaner | S1, S2 | MN1, MN2 | 4904 | node/255406873, Muntaner | 41 | `playable` |
| `MO` | Monistrol de Montserrat | R5, R50, R53 | MO1, MO2, MO3 | 335 | node/1928833209, Monistrol Enllaç (Cremallera) | 2 | `playable` |
| `MQ` | Masquefa | R6, R60, R63 | MQ1, MQ2 | 344 | node/9899950745, Masquefa | 13 | `playable` |
| `MS` | Mira-Sol | S1 | MS1, MS2 | 2443 | node/1394232465, Mira-sol | 35 | `playable` |
| `MV` | Martorell Vila | R53, R63, S4, S8 | MV1, MV2 | 597 | node/7515916373, Martorell - Vila / Castellbisbal | 67 | `playable` |
| `NA` | Terrassa Nacions Unides | S1 | NA1, NA2 | 2443 | node/3671928434, Terrassa Nacions Unides | 24 | `playable` |
| `NO` | Sabadell Nord | S2 | NO1, NO2 | 2461 | node/4380799238, Sabadell Nord | 27 | `playable` |
| `OL` | Olesa de Montserrat | R5, R50, R53, S4 | OL1, OL2, OL4 | 590 | node/307996313, Olesa de Montserrat | 28 | `playable` |
| `PA` | Pallejà | R5, R50, R53, R6, R63, S4, S8 | PA1, PA2 | 1197 | node/5331587812, Pallejà | 9 | `playable` |
| `PC` | Barcelona - Plaça Catalunya | S1, S2 | PC1, PC2, PC3 | 4904 | node/3673333976, Barcelona-Plaça Catalunya | 29 | `playable` |
| `PE` | Barcelona - Plaça Espanya | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | PE1, PE2, PE3, PE4 | 1489 | node/13575528247, Barcelona-Plaça Espanya | 21 | `playable` |
| `PF` | Peu del Funicular | S1, S2 | PF1, PF2 | 4904 | node/2981726993, Vallvidrera Inferior | 12 | `playable` |
| `PG` | Polígon industrial del Segre | RL1, RL2 | PG1 | 86 | node/11739285301, Polígon industrial del Segre | 14 | `playable` |
| `PI` | Piera | R6, R60, R63 | PI1, PI2 | 344 | node/350306783, Piera | 8 | `playable` |
| `PJ` | Sabadell Plaça Major | S2 | PJ1, PJ2 | 2461 | node/5357452240, Sabadell Plaça Major | 12 | `playable` |
| `PL` | El Palau | R5, R53, R6, R63, S4, S8 | PL1, PL2 | 1185 | node/2980154580, el Palau | 34 | `playable` |
| `PN` | Sabadell Parc del Nord | S2 | PN1, PN2 | 2461 | node/4380799272, Sabadell Parc del Nord | 27 | `playable` |
| `PO` | La Pobla de Claramunt | R6, R60, R63 | PO1, PO2 | 344 | node/390909355, la Pobla de Claramunt | 2 | `playable` |
| `PR` | Provença | S1, S2 | PR1, PR2 | 4904 | node/3398928337, Provença | 8 | `playable` |
| `PS` | La Pobla de Segur | RL2 | PS1 | 30 | node/279283063, la Pobla de Segur | 23 | `playable` |
| `PT` | Palau de Noguera | RL2 | PT1 | 30 | node/5420881259, Palau de Noguera | 9 | `playable` |
| `QC` | Quatre Camins | R5, R53, R6, R63, S4, S8, S9 | QC3, QC4 | 1197 | node/1839654661, Quatre Camins | 6 | `playable` |
| `RB` | Rubí Centre | S1 | RB1, RB2 | 2443 | node/9757864300, Rubí Centre | 25 | `playable` |
| `RM` | Térmens | RL1, RL2 | RM1 | 86 | node/1580677559, Térmens | 198 | `playable` |
| `SA` | Sant Andreu de la Barca | R5, R50, R53, R6, R60, R63, S4, S8 | SA1, SA2 | 1209 | node/1195505798, Sant Andreu de la Barca | 59 | `playable` |
| `SC` | Sant Cugat Centre | S1, S2 | SC1, SC2 | 4904 | node/7209331935, Sant Cugat Centre | 7 | `playable` |
| `SD` | Salàs de Pallars | RL2 | SD1 | 30 | node/4973964140, Salàs de Pallars | 0 | `playable` |
| `SE` | Sant Esteve Sesrovires | R6, R60, R63 | SE1, SE2 | 344 | node/9899950749, Sant Esteve Sesrovires | 10 | `playable` |
| `SG` | Sant Gervasi | S1, S2 | SG1, SG2 | 4904 | node/3398928343, Sant Gervasi | 3 | `playable` |
| `SJ` | Sant Joan | S2 | SJ1, SJ2 | 2461 | node/7209331936, Sant Joan | 4 | `playable` |
| `SM` | St. Llorenç de Montgai | RL2 | SM1 | 30 | node/3954397657, Sant Llorenç de Montgai | 5 | `playable` |
| `SN` | Santa Linya | RL2 | SN1 | 30 | node/1992661061, Santa Linya | 37 | `playable` |
| `SP` | Sant Josep | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | SP1, SP2 | 1489 | node/463272142, Sant Josep | 43 | `playable` |
| `SQ` | Sant Quirze | S2 | SQ1, SQ2 | 2461 | node/9767567865, Sant Quirze | 3 | `playable` |
| `SR` | Sarrià | S1, S2 | SR1, SR2 | 4904 | node/8075665237, Sarrià | 2 | `playable` |
| `SV` | Sant Vicenç-Castellgalí | R5, R50, R53 | SV1, SV2, SV4 | 335 | node/503198423, Sant Vicenç / Castellgalí | 2 | `playable` |
| `TP` | Tremp | RL2 | TP1 | 30 | way/401781088, Estació de Tremp | 6 | `playable` |
| `TR` | Terrassa - Rambla | S1 | TR1, TR2 | 2443 | node/3672285968, Terrassa Rambla | 33 | `playable` |
| `TT` | Les Tres Torres | S1, S2 | TT1, TT2 | 4904 | node/259649938, Les Tres Torres | 4 | `playable` |
| `UN` | Universitat Autònoma | S2 | UN1, UN2 | 2461 | node/2049475258, Universitat Autònoma | 18 | `playable` |
| `VA` | Vallbona d'Anoia | R6, R60, R63 | VA1, VA2 | 344 | node/9899950743, Vallbona d'Anoia | 43 | `playable` |
| `VB` | Vilanova de la Barca | RL1, RL2 | VB1 | 86 | node/5420775829, Vilanova de la Barca | 2 | `playable` |
| `VD` | Valldoreix | S1, S2 | VD1, VD2 | 4904 | node/9757864307, Valldoreix | 3 | `playable` |
| `VF` | Vallfogona de Balaguer | RL1, RL2 | VF1 | 86 | node/5420775821, Vallfogona de Balaguer | 78 | `playable` |
| `VH` | Sant Vicenç dels Horts | R5, R50, R53, R6, R60, R63, S3, S4, S8, S9 | VH1, VH2, VH3 | 1489 | node/7515916370, Sant Vicenç dels Horts | 2 | `playable` |
| `VI` | Manresa Viladordis | R5, R50, R53 | VI1 | 335 | node/5359591632, Manresa-Viladordis | 34 | `playable` |
| `VL` | Baixador de Vallvidrera | S1, S2 | VL1, VL2 | 4904 | node/9757864310, Baixador de Vallvidrera | 3 | `playable` |
| `VN` | Vilanova del Camí | R6, R60, R63 | VN1, VN2 | 344 | node/9899895971, Vilanova del Camí | 67 | `playable` |
| `VO` | Volpelleres | S2 | VO1, VO2 | 2461 | node/5418191428, Volpelleres | 7 | `playable` |
| `VP` | Vallparadís Universitat | S1 | VP1, VP2 | 2443 | node/13307321594, Vallparadís Universitat | 4 | `playable` |

### Deferred Routes

| Routes | GTFS type | Decision |
| --- | ---: | --- |
| L6, L7, L8, L12 | 1 | Metro deferred |
| FV, L1, MM | 7 | Funicular/rack services deferred |
| BusBV | 3 | Replacement bus deferred |
