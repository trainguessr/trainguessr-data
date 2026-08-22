# Norway

Station source: Entur's National Stop Register, filtered to active railway
stations and queried with the required `ET-Client-Name` request header.

Runtime source: Entur Journey Planner GraphQL API. Railway departures use the
station's `quay.publicCode` when available so the board can expose the platform
reported by Entur.

Generate the station list from the data repository root:

```shell
python3 gen/norway.py
```

The optional `--input` argument accepts a saved National Stop Register response
for an offline rebuild. Active cross-provider records and reviewed names are
maintained in `excludes/norway.json`.

Entur requires a meaningful `ET-Client-Name` header. Retain Entur attribution
and comply with the Norwegian Licence for Open Government Data (NLOD) terms.
