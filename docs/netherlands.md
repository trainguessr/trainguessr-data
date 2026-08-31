# Netherlands

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Netherlands | `netherlands_all` | Rijden de Treinen / NS and other Dutch operators | `gen/netherlands.py` | 397 nodes. Rijden de Treinen describes its NL catalogue as all Dutch railway stations, sourced directly from NS and refreshed for station openings, closures, and renames. The data includes two `facultatiefStation` records. Metro/tram is separate. |

## Generation and source notes

Station data comes from [Rijden de Treinen open data](https://www.rijdendetreinen.nl/en/open-data).
Its API supplies live departures.

Run `python3 gen/netherlands.py` from the repository root.


## Attribution and provider constraints

- Stations: [Rijden de Treinen open station data](https://www.rijdendetreinen.nl/en/open-data/stations), CC0.
- Live boards: Rijden de Treinen consumer endpoint.
- Constraint: get permission for the undocumented live endpoint or migrate to an authorized API.


## Other providers

No new heavy-rail provider is needed for the existing-provider checkpoint. Metro/light rail is deferred to the secondary-mode phase.
