# Sweden

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Sweden | `sweden_all` | Trafiklab ResRobot | `gen/sweden.py` | 839 nodes: 739 rail and 100 metro. Trafiklab’s national stop data/ResRobot covers all Swedish operators, uses the same national `740...` stop IDs as GTFS Sverige 2, and refreshes when source data changes. The generator has no current-trip gate. Ordinary tram expansion is out of scope; the existing provider covers metro. |

## Generation and source notes

Trafiklab has station and departure data in its Stops and ResRobot
APIs. A valid Stops-data API key is required. Request one from
[Trafiklab](https://www.trafiklab.se/) and set it in `.env-secret`:
`export TRAFIKLAB_API_KEY_STOPS=...`.

Once you have your API key, run `python3 gen/sweden.py` from the repository root.

Given the low rate of requests allowed by the Trafiklab API, the script caches the
source archive and derived files under `cache/sweden/`: `stops.zip`, `_stops.xml`,
`sweden_full.json`, and `sweden_jlines.json`. To force a complete refresh, remove
those four files and rerun the root-level command. The `yq` command-line tool is
required when the derived JSON files need to be rebuilt.

The generator rejects non-Swedish national stop identifiers. The 32 foreign records found in the current dataset were moved to `overrides/exclusions/sweden.json`.


## Attribution and provider constraints

- Stations: Trafiklab Stops data.
- Live boards: Trafiklab ResRobot.
- License: CC0 1.0 for the documented datasets.
- Constraint: use registered account keys, observe quotas, and do not imply Trafiklab or Samtrafiken endorsement.


## Other providers

The existing provider covers national rail and metro. Ordinary tram expansion is out of scope; only a railway-like light-rail exception may be considered later.
