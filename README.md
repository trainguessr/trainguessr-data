# Trainguessr railway stations dataset

This repository contains a dataset of geolocated railway stations across various European countries, along with scripts to generate and update the data.

This README provides information about the data sources used for each country, instructions on how to generate the datasets, and notes on any removed or renamed stations.

## Repository layout

Run generators from this repository's root with `python3 gen/<country>.py` when
their section documents root-relative paths. Older scripts that use `../`
paths must be run from `gen/`, as noted in their sections.
Downloaded and intermediate source files belong under the ignored `cache/`
directory, normally grouped as `cache/<country>/`. Playable station lists are
written to `nodes/nodes-*.json`. Generated runtime assets that are not NDJSON,
such as the Spain SQLite schedule index and geo-near cache, belong under the
root `cache/` directory. Do not commit API keys or downloaded source archives.

## Data sources

### Austria

Austria uses ÖBB SCOTTY for live boards. The station catalogue keeps the existing [ÖBB GeoNetz](https://data.oebb.at/de/datensaetze~geo-netz~) EVA IDs and fills private/regional rail gaps from the nationwide [MVO stop dataset](https://mobilitaetsdaten.gv.at/en/daten/%C3%B6sterreichweite-haltestellen). New MVO stops are accepted only when they resolve unambiguously to a SCOTTY station.

Run `python3 austria.py` from `gen/` to preserve the GeoNetz catalogue and automatically enrich it from the official public MVO sample. Set `MVO_USERNAME` and `MVO_PASSWORD` to use the current authenticated production snapshot, or pass `--mvo-input` to use a reviewed MVO ZIP containing `haltestellen.csv` and `steige.csv`. Dataset scope and known limitations are recorded in `sources/austria-dataset-coverage.json`.

### Belgium

Infrabel exports its stations as open data in a JSON file [here](https://opendata.infrabel.be/explore/dataset/operationele-punten-van-het-netwerk/export/?sort=ptcarid).

Trainguessr uses the iRail API ([here](https://docs.irail.be/#)) as it makes things way easier. Stations and live departures are obtained from the iRail API, which is a public API that does not require an API key.

Run `cd gen && python3 belgium.py` because this legacy script uses `../nodes/`.

### France

SNCF exports its stations as open data in a JSON file [here](https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe%2FBerlin).

These station IDs are then used in the SNCF API, which requires an API key. The API key is obtained by creating a free account on the SNCF Numerique website: [SNCF Numerique](https://numerique.sncf.com/).

Run `python3 gen/france.py` from the repository root. The generator refreshes a
cache older than seven days; use `--refresh` to force a download. The API key is
not needed to generate stations, only for live departures.

The reviewed French section of Cuneo-Ventimiglia is supplemented from
`sources/france/cuneo-ventimiglia.json`. SNCF remains the primary live source;
the recorded RFI board IDs are explicit fallbacks.


### Finland

Finnish passenger stations can be generated from Fintraffic's official station metadata endpoint with `python3 gen/finland.py`. The station short code is used as the ID so it can later be used by the real-time railway API. A saved official response can be supplied with `--input`.

### Germany

The German railway system is a bit of a mess. The Deutsche Bahn API is not public, but it is possible to get the real time departures from the DB website: [DB](https://www.bahnhof.de/api/boards). The list of stations is obtained from the DB open data website: [DB Open Data](https://data.deutschebahn.com/). It thankfully uses UIC codes.

Run `python3 gen/germany.py`. It automatically downloads the current `db-stations` package from npm when `cache/germany/full.json` is missing, validates and caches the source files, and reports the age of an existing cache on every run. `gen/germany.sh` is retained as a compatibility wrapper.

### Italy

Italy uses one dataset for each infrastructure provider. Run the command in the last column from the repository root. Each command downloads its source, stores working files in `cache/italy/<provider>/`, validates the result, and overwrites one file in `nodes/`.

| Provider | Downloaded source | Output | Command |
| --- | --- | --- | --- |
| RFI | [RFI arrivals and departures](https://iechub.rfi.it/ArriviPartenze/ArrivalsDepartures/Home) | `nodes/nodes-italy-rfi.json` | `python3 gen/italy_rfi.py` |
| Ferrovienord (FN) | [Trenord real-time page](https://www.trenord.it/linee-e-orari/circolazione/tempo-reale/) | `nodes/nodes-italy-fn.json` | `python3 gen/italy_fn.py` |
| Trentino Trasporti (TT) | [Official GTFS](https://www.trentinotrasporti.it/opendata/google_transit_extraurbano_tte.zip) | `nodes/nodes-italy-tt.json` | `python3 gen/italy_tt.py` |
| Ferrovie Emilia Romagna (FER) | FER PittiInfo line pages | `nodes/nodes-italy-fer.json` | `python3 gen/italy_fer.py` |
| Ente Autonomo Volturno (EAV) | [EAV train information](https://orariotreni.eavsrl.it/) | `nodes/nodes-italy-eav.json` | `python3 gen/italy_eav.py` |
| Ferrovie del Sud Est (FSE) | OpenStreetMap and ViaggiaTreno | `nodes/nodes-italy-fse.json` | `python3 gen/italy_fse.py` |

The FN, TT, FER, EAV, and RFI datasets contain reviewed coordinates from the committed node files. Their generators match current provider records to these reviewed records by exact ID. New provider records without reviewed coordinates stay out of the playable dataset and appear in `cache/italy/<provider>/reports/audit.csv`.

TT still uses numeric IDs from its former real-time service. The official GTFS does not publish these IDs. `gen/italy_tt.py` keeps the IDs from `nodes/nodes-italy-tt.json` and downloads the current GTFS for source review.

FSE uses ViaggiaTreno IDs and OSM coordinates. Its unresolved records and audit are in `cache/italy/fse/reports/`. Stations served by FSE and managed by RFI remain in the RFI dataset.

To review all five conservative rebuilds without changing `nodes/`, run `python3 gen/italy_legacy.py all --dry-run` after their source files exist in `cache/italy/`.

#### Interactive review

Each Italian generator starts an interactive review after it writes and validates its dataset. The review starts when the command runs in a terminal. It asks only about new or changed items.

Available decisions include entering missing coordinates, excluding a provider record, retaining a reviewed station, keeping a reviewed name, and accepting a current provider name. You can defer any item. You can also confirm all remaining name differences for one provider with one choice.

Decisions are stored in `excludes/italy.json`:

- Coordinate entries are stored in `manual_stations` and are restored by later generations.
- Exclusions are stored in `excluded`.
- Name and retention confirmations are stored in `reviews` with the source and reviewed names. A changed source record creates a new question.

Run the review queue again without downloading data:

```bash
python3 gen/italy_review.py all
python3 gen/italy_review.py rfi
```

Automation can disable terminal review while keeping reports and validation:

```bash
TRAINGUESSR_SKIP_REVIEW=1 python3 gen/italy_rfi.py
```

### Netherlands

Just like Sweden, the Netherlands has tremendous support for open data. The data was downloaded from the Rijden de Treinen website: [Rijden de Treinen](https://www.rijdendetreinen.nl/en/open-data). Their API is also used to get the real-time departures.

Run `cd gen && python3 netherlands.py` because this legacy script uses `../cache/` and `../nodes/`.

### Norway

Norwegian railway stations are generated from Entur's National Stop Register
using `python3 gen/norway.py`. The generator requests active rail stations with
the required `ET-Client-Name` header and writes `nodes/nodes-norway.json`.
The optional `--input` argument accepts a saved Entur response for an offline
rebuild. Source and runtime details are recorded in `sources/norway.md`.

### Spain

Spain uses the official Renfe Cercanias/Rodalies and long-/medium-distance and
high-speed GTFS archives. Run the generator from the repository root:

```bash
python3 gen/spain.py
```

The generator downloads current official archives into `cache/spain/`, then
generates `nodes/nodes-spain-renfe.json` and the disk-backed runtime index
`cache/spain.sqlite`. Use the `--cercanias`, `--long-distance` and
`--no-download` options when rebuilding from reviewed local archives.

Downloaded GTFS archives are intentionally ignored by Git. Deploy
`cache/spain.sqlite` alongside the `nodes/` directory in the data volume. When
production uses `DATA_DIR=/data/nodes` and `DATA_CACHE_DIR=/data/cache`, the
application reads `/data/cache/spain.sqlite`. Exact source URLs and attribution
requirements are recorded in `sources/spain.md`.

### Denmark

Denmark uses the official Rejseplanen Labs GTFS Schedule/Static feed and API
2.0. The static feed is available at
<https://www.rejseplanen.info/labs/GTFS.zip>. API 2.0 access requires an
approved Labs request; non-commercial use is free up to 50,000 calls/month.
Request access at
<https://labs.rejseplanen.dk/hc/requests/new?ticket_form_id=17536468593565>.

Set `REJSEPLANEN_API_KEY` in the environment (the application `.env-secret`
already supplies it in development) and run from the repository root:

```bash
python3 gen/denmark.py
```

The script downloads the static archive to `cache/denmark/`, normalizes
zero-padded Rejseplanen stop IDs, writes `nodes/nodes-denmark.json`, and
smoke-tests both departure and arrival boards with the configured key.

### Switzerland

Switzerland has a very good API for its stations. The data is available in JSON format and can be obtained from the SBB Open Data website: [SBB API](https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson)

Once the IDs are gathered, they can be used in the Transport API, which relies on the same IDs: [Transport CH](https://transport.opendata.ch/).

Run `cd gen && python3 switzerland.py` because this legacy script writes through `../nodes/`.

### Sweden

Sweden has a great, all-encompassing API service for its stations and departures called Trafiklab. The API provides access to real-time data and is user-friendly, making it easy to integrate into applications.

It requires a valid API key, which can be obtained by signing up on the Trafiklab website: [Trafiklab](https://www.trafiklab.se/). Add your API key to the `.env-secret` file: `export TRAFIKLAB_API_KEY_STOPS=...`. Remember to use the correct "Stops data" API key since Trafiklab provides different keys for different datasets.

We downloaded the Stops dataset to get the stations. Some stations had to be removed, in particular, those situated outside of Sweden.

Once you have your API key, run `cd gen && python3 sweden.py` because this legacy script uses `../cache/` and `../nodes/`.

Given the low rate of requests allowed by the Trafiklab API, the script will cache the GTFS dataset locally in the `cache/` folder. If you want to refresh the cache, just delete the `cache/sweden.zip` file.

The generator rejects non-Swedish national stop identifiers. The 32 foreign records found in the current dataset were moved to `excludes/sweden.json`.

### United Kingdom

The UK has a million different services exposing train data, which is fortunate since the UK does not have a national rail service; rather, several operators run the trains. Yet, National Rail uses an airport-like system to identify stations, which is very useful to us and is the one we use.

The lists of stations are roughly public and can be downloaded from several sources, like from [Railway Codes](http://www.railwaycodes.org.uk/crs/crs0.shtm). Ours comes from this repository: [UK Railway Stations](https://github.com/davwheat/uk-railway-stations).

The API endpoint we use to get the real-time departures is Huxley2: [Huxley2](https://huxley2.azurewebsites.net/).

Run `cd gen && python3 uk.py` because this legacy script uses `../cache/` and `../nodes/`.

## Removed stations

### Belgium

The `excluded` list in `excludes/belgium.json` contains the stations that were removed. These stations lie outside of Belgium but are included in the NMBS/SNCB network. They are used for international connections, especially to France.

The script that generates the Belgium stations (`gen/belgium.py`) automatically removes these stations.

### Italy

The `excluded` list in `excludes/italy.json` records removed stations and their reasons. Entries can name an operator.

### Sweden

The `excluded` list in `excludes/sweden.json` contains the stations that were removed. These stations lie outside of Sweden but are included in the Trafikverket network. They are used for international connections, especially to Denmark and Germany.

The script that generates the Sweden stations (`gen/sweden.py`) automatically removes these stations.

All active Swedish records now use the Swedish `740` national stop prefix.

### Switzerland

The Switzerland dataset only contains stations within Switzerland, so no removal was necessary.

## Renamed stations

Each country file in `excludes/` has a `renamed` list. Italy entries may also specify an operator. These names avoid ambiguity between countries and operators.

## Future expansion

### Italy

Several rail infrastructure managers exist in Italy apart from RFI. These smaller companies manage regional railways and often have their own APIs or data sources. However, gathering data from all these different sources is challenging to say the least.

| Rail infrastructure manager           | Railways                                                        |
| ------------------------------------- | --------------------------------------------------------------- |
| Società Subalpina Imprese Ferroviarie | Domodossola-Locarno (from Ribellasca to Domodossola)            |
| Agenzia Mobilità e Trasporti          | Principe-Granarolo, Genova-Casella                              |
| Strutture Trasporto Alto Adige        | L'Assunta-Collalbo, Merano-Malles                               |
| Infrastrutture Venete                 | Adria-Mestre                                                    |
| Rete Ferroviaria Toscana              | Arezzo-Stia, Arezzo-Sinalunga                                   |
| ASTRAL                                | Roma-Civita Castellana-Viterbo, Roma Lido                       |
| ATAC                                  | Roma-Giardinetti (closed since 2025)                            |
| Ferrovia Adriatico Sangritana         | Ferrovia Sangritana                                             |
| Ferrovie del Gargano                  | San Severo-Peschici, Foggia-Lucera                              |
| Ferrotramviaria                       | Bari-Barletta, Bari-San Paolo                                   |
| Ferrovie Appulo Lucane                | Bari-Matera-Montalbano Jonico, Altamura-Avigliano-Potenza       |
| Ferrovie della Calabria               | tante                                                           |
| ARST                                  | Macomer-Nuoro, Monserrato-Isili, Sassari-Alghero, Sassari-Sorso |
| FCE                                   | Paternò-Riposto (Circumetnea)                                   |

The Domodossola-Locarno line is managed by Società Subalpina Imprese Ferroviarie (SSIF) and connects Italy to Switzerland. SSIF links with the Swiss Federal Railways (SBB) in Switzerland territory and those stations are already included in the Switzerland dataset; however, the Italian stations are missing (from Ribellasca to Domodossola).

## Other countries

| Country | Operator | Notes |
| --- | --- | --- | 
| Portugal | Comboios de Portugal (CP) | Still to find official GTFS feed or API |
| Czech Republic | České dráhy | HAFAS-based APIs should be available, but a mess to implement |
| Poland | PKP | Still to research |

## Maintenance commands

Run these commands from the repository root:

```bash
python3 gen/validate_all.py
python3 -m unittest discover -s tests -v
```

## Contributing

Contributions to this dataset are welcome! If you find any errors, missing stations, or have suggestions for improvements, please open an issue or submit a pull request.

When submitting changes, please ensure that you provide clear explanations and references for any modifications made to the dataset. This will help maintain the accuracy and reliability of the data for all users.

Italian generators must use exact IDs or reviewed mappings. Inspect `cache/italy/<provider>/reports/audit.csv` before accepting station changes.

## License

A vast majority of the data sources used in this dataset are open data or publicly accessible APIs. The overall dataset is licensed under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1.0/) and has been compiled with data from OpenStreetMap and other open data sources. Please refer to the individual data sources for their specific licensing terms.

The data that was scraped from websites without public APIs is intended for personal and non-commercial use only. Please respect the terms of service of the original data providers when using this dataset.

The canonical provider attribution and terms summary is maintained in
[`ACKNOWLEDGMENTS.md`](ACKNOWLEDGMENTS.md).
