# United Kingdom

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| United Kingdom | `uk_national_rail` | National Rail Darwin, with Huxley2 fallback | `gen/uk.py` | 2,608 nodes. The upstream catalogue contains 2,608 stations queryable through National Rail Darwin, including Cambridge South (`CMS`) and Beaulieu Park (`BPA`). Northern Ireland Railways and heritage/private systems are future-provider entries; metro is deferred. |

## Generation and source notes

National Rail uses CRS station codes across the UK operators. The station list
comes from [UK Railway Stations](https://github.com/davwheat/uk-railway-stations).
Live departures use National Rail Darwin when configured, with [Huxley2](https://huxley2.azurewebsites.net/)
as the fallback.

Run `python3 gen/uk.py` from the repository root.


## Attribution and provider constraints

- Stations: `davwheat/uk-railway-stations`, Trainline EU, and upstream contributors under ODbL.
- Live boards: National Rail Darwin when configured, otherwise Huxley2 as an independent proxy.
- Attribution: Source: National Rail Darwin for live railway information; keep the station-data attribution chain and ODbL share-alike.
- Constraint: public use requires the deployer's own Rail Data Marketplace subscription and accepted terms. Do not rely on the public Huxley2 demo for production.


## Other providers

Northern Ireland Railways and private/heritage rail need future providers. Underground, Glasgow Subway, Tyne & Wear Metro, and tram systems are deferred to the secondary-mode phase.
