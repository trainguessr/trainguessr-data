# Germany

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Germany | `germany_all` | Deutsche Bahn Timetables/bahnhof boards | `gen/germany.py` and `docs/review/germany-reconciliation.json` | 6,652 nodes: 5,388 cached DB records, 33 AKN supplements, and 1,231 current-provider DB EVA additions. The audit records 7 explicit current-provider gaps, 54 separate-system candidate records, and 40 stale catalogue IDs for lifecycle review; U-Bahn/tram is separate. |

## Generation and source notes

The live board source is the Deutsche Bahn website API
([DB](https://www.bahnhof.de/api/boards)). Station data comes from [DB Open
Data](https://data.deutschebahn.com/) and uses UIC codes.

Run `python3 gen/germany.py`. It automatically downloads the current `db-stations` package from npm when `cache/germany/full.json` is missing, validates and caches the source files, and reports the age of an existing cache on every run. The generator also appends the reviewed current-provider DB EVA additions recorded in `docs/review/germany-reconciliation.json`; the source and cache-coverage limits are documented in `docs/germany.md`.


## Runtime identity

`germany_all` uses Deutsche Bahn EVA IDs. The live adapter requests the official
DB Timetables API with `DB_API_TIMETABLES_CLIENTID` and
`DB_API_TIMETABLES_SECRET` (the legacy `DB_API_RISBOARDS_*` names are
accepted by the application). A direct `/station/{eva}` response with `db=true`
and a successful `/plan/{eva}/...` response are the required identity checks.

## Current heavy-rail reconciliation

`gen/germany.py --audit` compares the current GTFS.de/DELFI `route_type=2`
feed with the DB station namespace, the generated nodes, and sampled official DB
station/plan responses. The captured feed is
`cache/germany/rv-latest.zip` with SHA-256
`c97933c005553e271e9ae64e37a4aadcf43c24d5d8ef95961db0a9d7acb3129e`.

With the DB credentials loaded, a cached audit can be rerun without repeating
successful probes:

```bash
source ../trainguessr/.env-secret
python3 gen/germany.py --audit --probe-stale-osm --progress
```

The feed contains 963 rail routes, 108,688 rail trips, and 7,737 rail parent
stop places. The precise Germany boundary contains 6,602 passenger candidates;
1,135 records are out of scope, including 208 non-boarding rail points. The
reconciliation record in `docs/review/germany-reconciliation.json` currently
reports:

- 1,264 verified additions to the existing DB provider, all backed by `db=true`
  and a sampled HTTP 200 DB plan response;
- 5,212 places already represented;
- 65 reviewed station-complex aliases;
- 7 explicit current-provider gaps;
- 54 separate heritage/tourist-provider candidate records;
- no unresolved current-provider records.

The generated catalogue now contains 6,652 unique Germany nodes: 5,388 cached
DB records, 33 legacy AKN supplements, and 1,231 current-provider additions. The
generator appends only `added_existing_provider` records from the audit and
keeps their provenance in the node `source` tag.

The seven provider gaps are explicit reviewed outcomes. Two are
Karlsruhe urban-rail identities requiring a KVV provider, four are route-20
Regensburg street records whose GTFS `route_type=2` classification has no DB
identity, and one Steinfeld record has a verified DB candidate whose physical
coordinates do not match the GTFS stop.

## Stale catalogue IDs

The cached catalogue has 34 primary IDs and 6 alias IDs absent from the current
DB namespace. They are recorded in the audit rather than deleted.
The current stale-ID partition is 2 `dismantled_exclusion`, 21
`provider_gap`, and 17 `unresolved`. The unresolved set is conservative;
failed or empty physical-evidence queries never authorize deletion or a guessed
replacement EVA ID. The captured OSM cache contains 224 nearby features from
40 records, with 21 failed endpoint attempts across seven batches; those
records are unresolved rather than treated as absent. No Germany
exclusions were added from this audit.

U-Bahn, tram, foreign, and operator-specific systems are outside the DB
heavy-rail provider until their own provider identities are verified. The
separate-system backlog is recorded in `docs/README.md`.

Sources:

- [GTFS.de Germany feeds](https://gtfs.de/en/feeds/germany/)
- [DB Timetables API](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables)
- [DB station data](https://github.com/derhuerst/db-stations)
- [GADM country boundaries](https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_DEU_0.json)
- [OpenStreetMap Overpass API](https://overpass-api.de/)

## Attribution and provider constraints

- Stations: Deutsche Bahn open data via `db-stations`.
- Physical discovery and regional supplements: GTFS.de/DELFI GTFS feed, with the feed's DELFI e.V. and GTFS.de attribution, plus OpenStreetMap contributors through bounded Overpass captures under ODbL.
- Live boards: official Deutsche Bahn Timetables API.
- Attribution: Source: Deutsche Bahn AG, CC BY 4.0, including `db-stations` notices.
- Constraint: use an API subscription and observe published request limits.


## Other providers

Private/heritage systems and a small set of DB-incompatible current candidates require separate provider work. U-Bahn and ordinary tram systems are outside the current heavy-rail provider.
