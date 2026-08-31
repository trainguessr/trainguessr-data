# Switzerland

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Switzerland | `switzerland_all` | Search.ch stationboard / Swiss Transport API | `gen/switzerland.py` | 1,697 current `TRAIN` service-point nodes. Swiss service-point v2 also publishes full past/future validity records; the generator reads current service points and filters `meansoftransport=TRAIN`. Non-TRAIN and historical records need proof of a physical passenger station addressable by search.ch. |

## Generation and source notes

Station data is available as GeoJSON from the [SBB Open Data
API](https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson).

Once the IDs are gathered, they can be used in the Transport API, which relies on the same IDs: [Transport CH](https://transport.opendata.ch/).

Run `python3 gen/switzerland.py` from the repository root.


## Attribution and provider constraints

- Stations: opentransportdata.swiss / SBB stop data.
- Live boards: search.ch timetable API.
- Attribution: cite opentransportdata.swiss and keep published station data current.
- Constraint: confirm public-product use with search.ch or migrate to an authorized opentransportdata.swiss API.


## Other providers

No new heavy-rail provider is needed for the current TRAIN namespace. Non-TRAIN/historical service points need physical/provider proof before inclusion.
