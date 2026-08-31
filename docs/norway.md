# Norway

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Norway | `norway_all` | Entur Journey Planner / National Stop Register | `gen/norway.py` | 367 active rail nodes. Entur requires stops in use to be ACTIVE and publishes nightly current, future, and all-version/outdated NeTEx dumps with stable NSR IDs. The generator excludes INACTIVE records pending historical and physical review. Metro/tram is deferred. |

## Generation and source notes

Norwegian railway stations are generated from Entur's National Stop Register
using `python3 gen/norway.py`. The generator requests active rail stations with
the required `ET-Client-Name` header and writes `nodes/nodes-norway.json`.
## Detailed review notes

Station source: Entur's National Stop Register, filtered to active railway
stations and queried with the required `ET-Client-Name` request header.

Runtime source: Entur Journey Planner GraphQL API. Railway departures use the
station's `quay.publicCode` when available so the board can show the platform
reported by Entur.

Generate the station list from the data repository root:

```shell
python3 gen/norway.py
```

The optional `--input` argument reads a saved National Stop Register response
for an offline rebuild. Active cross-provider records and reviewed names are
kept in `overrides/exclusions/norway.json`.

Entur requires a meaningful `ET-Client-Name` header. Include Entur attribution
and comply with the Norwegian Licence for Open Government Data (NLOD) terms.

## Attribution and provider constraints

- Stations: Entur National Stop Register.
- Live boards: Entur Journey Planner.
- Attribution: Data made available by Entur under NLOD.
- Constraint: identify requests with `ET-Client-Name` and include Entur attribution.


## Other providers

No new heavy-rail provider is needed for active NSR rail stops. Historical/inactive physical stations need more evidence; metro/light rail is deferred.
