# Finland

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Finland | `finland_all` | Fintraffic Digitraffic | `gen/finland.py` and `docs/review/finland-reconciliation.json` | 222 nodes, including 13 no-current-traffic station sites. The audit has 262 official operational/non-passenger outcomes and 24 explicit unresolved possible-former-passenger sites; Helsinki metro/tram requires HSL or another separate provider. |

## Generation and source notes

Finnish passenger stations can be generated from Fintraffic's official station metadata endpoint with `python3 gen/finland.py`. The station short code is used as the ID so it can later be used by the real-time railway API. A saved official response can be supplied with `--input`. The no-current-traffic physical reconciliation is generated with `python3 gen/finland.py --audit`; its complete per-record outcomes, including current and versioned infrastructure evidence, are stored in `docs/review/finland-reconciliation.json`.


## Fintraffic Digitraffic

TrainGuessr uses the official Fintraffic Digitraffic railway metadata and live
train APIs. The station short code is the native runtime station identifier.

- Metadata: <https://rata.digitraffic.fi/api/v1/metadata/stations>
- Passenger GTFS: <https://rata.digitraffic.fi/api/v1/trains/gtfs-passenger-stops.zip>
- Infrastructure register: <https://rata.digitraffic.fi/infra-api/latest/rautatieliikennepaikat.json?count=4000>
- Infrastructure station parts: <https://rata.digitraffic.fi/infra-api/latest/liikennepaikanosat.json?count=4000>
- Infrastructure person platforms: <https://rata.digitraffic.fi/infra-api/latest/laiturit.json?count=4000>
- Runtime boards: <https://rata.digitraffic.fi/api/v1/live-trains/station/{station_code}>

The generator sends the existing `Digitraffic-User` header and uses Python
`requests`. Running `python3 gen/finland.py` succeeded on 2026-08-27 with HTTP
200 and did not require a credential. A prior ad-hoc request returned HTTP 406;
that result was request-specific and did not show an authentication
requirement.

Run from the data-repository root:

```shell
python3 gen/finland.py
python3 gen/finland.py --input path/to/stations.json
```

The physical reconciliation is generated separately. It uses the full current
infrastructure register, optional saved OSM/Overpass captures, the versioned
infrastructure register, and every candidate's native live-board code:

```shell
python3 gen/finland.py --audit --probe-live \
  --refresh-history \
  --osm-input path/to/osm-rail-nodes.json \
  --osm-input path/to/osm-platforms.json
```

Official source responses are cached under `cache/finland/`. Overpass access is
optional; `--overpass-bbox` uses split requests, retries, and rotating public
instances. A failed OSM request is recorded and does not turn into a guessed
station decision. The historical infrastructure endpoint accepts data from
2010 onward and requires gzip compression; the reconciler stores its response
in `cache/finland/rautatieliikennepaikat-history.json`.

## Physical-station review

The metadata response contained 563 records, including 552 Finnish records:
209 with `passengerTraffic=true`, 343 with `passengerTraffic=false`, and 44
turnouts. The generator includes all 209 passenger-traffic records and 13 high-confidence
`passengerTraffic=false` station sites, producing 222 nodes. The review uses
the official infrastructure register, OSM/Overpass physical evidence, and
Digitraffic native-code responses. Empty traffic is not treated as deletion
evidence.

The eight reviewed native IDs are:

| ID | Station | Evidence |
| --- | --- | --- |
| `HYT` | Hyvinkää tavara | OSM station and two platforms; `train=yes`. |
| `IOA` | Ilola | OSM halt with matching UIC reference. |
| `KOI` | Kovjoki | OSM platform with `train=yes`; current infrastructure record. |
| `LO` | Lohja | OSM stop with `train=yes`; current infrastructure record. |
| `PP` | Pihtipudas | OSM platform with `train=yes`; current infrastructure record. |
| `UKP` | Uusikaupunki | OSM platform; current infrastructure record. |
| `VI` | Valkeakoski | OSM platform; current infrastructure record. |
| `VKT` | Vuokatti | Named OSM platform; current infrastructure record. |

The complete candidate reconciliation is in
`docs/review/finland-reconciliation.json`. It covers all 299 Finnish
`STATION`/`STOPPING_POINT` records with `passengerTraffic=false`:

- 13 `added_existing_provider` records consist of the eight
  manually reviewed sites plus five records with current commercial
  Digitraffic stop events (`ILR`, `NOK`, `OLT`, `ORI`, `TPET`).
- 262 `not_passenger_station` records have current official infrastructure
  evidence for an operational point without an exact person platform. This
  includes 208 traffic places without a passenger facility, 28 station parts
  without an exact person platform, and 26 records with official operational
  name markers such as `tavara`, `lajittelu`, `raja`, or `satama`.
- 24 records have explicit `unresolved` outcomes. They are current official
  permission places (`lupapaikka=true`) where former passenger use is
  plausible and the supplied evidence does not show a playable facility.
- The audit has no `dismantled_exclusion`, `provider_gap`, or provider-error
  status. Every row includes its native metadata identity, infrastructure
  match, historical match where available, nearby OSM evidence, and live-board
  result where probed.

The 44 records whose metadata type is `TURNOUT` are not passenger stations and
are outside this 299-record reconciliation. No Finland IDs were written to
`overrides/exclusions/finland.json`.

The official passenger GTFS contains 929 stops and 204 parent stations. It does
not include the no-current-traffic records; six `passengerTraffic=true` records
(`HH`, `HSI`, `KIA`, `NLÄ`, `PRV`, `VNA`) are also absent from that current
passenger GTFS and are included from official metadata pending separate
review.

Helsinki metro and tram are not Digitraffic railway-provider records. They
require a separate HSL/secondary-mode investigation and must not be assigned
Fintraffic station IDs.

The eight original manual decisions are in `overrides/finland-review.json`;
the full reproducible outcome ledger, including the 1,268-record historical
source capture, is
`docs/review/finland-reconciliation.json`.

## Attribution and provider constraints

- Stations and live boards: [Fintraffic Digitraffic](https://www.digitraffic.fi/en/railway-traffic/).
- Attribution: Source: Fintraffic / digitraffic.fi, CC BY 4.0, with source, license, and modification notice.


## Other providers

Helsinki metro is a future separate-provider/mode item. Tram is out of the completeness target. No new heavy-rail provider is currently being added.
