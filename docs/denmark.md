# Denmark

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Denmark | `denmark_all` | Rejseplanen GTFS/API 2.0 | `gen/denmark.py` | 631 nodes, including 173 current Letbane stop IDs. Current provider/operator services are listed in `docs/denmark.md`; 44 metro stops are assigned to a later mode phase. |

## Generation and source notes

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
Use `python3 gen/denmark.py --offline` to rebuild from the checked-in cache
without network or API-key access.


## Rejseplanen provider

Static source: official Rejseplanen Labs GTFS Schedule (Static), refreshed on
an approximately two-week cycle: <https://www.rejseplanen.info/labs/GTFS.zip>.
Runtime source: Rejseplanen API 2.0 departure/arrival boards at
<https://www.rejseplanen.dk/api>. Both require approved Labs access and
`REJSEPLANEN_API_KEY`; credentials are never stored in this repository.

The checked-in snapshot covers `20260810` through `20261104` and contains
1,589 routes, 36,309 stops, 173,685 trips, and 4,113,661 stop-times. The
generator keeps provider stop IDs beginning with `86` when they occur in
selected provider rail services. Heavy-rail IDs are commonly seven digits;
Letbane IDs are longer and use the same Rejseplanen namespace.

## Included service families

The current feed contains these provider/operator services:

- DSB conventional rail (`route_type=2`);
- DSB S-tog (`route_type=109`);
- Lokaltog A/S, GoCollective, Midttrafik, NT, Skånetrafiken, and Snälltåget
  conventional rail services (`route_type=2`);
- Aarhus Letbane L1/L2, operated in the feed by Midttrafik;
- Odense Letbane L;
- Hovedstadens Letbane L.

The four current `route_type=0` Letbane services are provider-supported and
are included immediately in `denmark_all`; their 173 provider stop IDs are
not written to `overrides/exclusions/denmark.json`. The runtime parser accepts `Letbane`
products as rail journeys.

The feed also contains four Metroselskabet `route_type=1` metro routes and
their 44 stop IDs. Metro is documented provider-supported coverage but is
outside this heavy-rail/Letbane category until the later metro phase. No metro
IDs are written to exclusions.

Bus (`route_type=3`, `700`, or `715`), ferry (`route_type=4`), replacement-bus,
and other non-rail records are not station candidates for `denmark_all`.

## Completeness and gaps

The offline rebuild produces 631 nodes: 458 conventional/S-tog
nodes plus 173 Letbane stop IDs. There are no explicit Denmark exclusions or
reviewed provider-ID mappings.

The current snapshot contains 567 additional `86...` stop records not used by
selected rail trips. They are a mixed set of bus, ferry, replacement-bus,
metro, inactive, and other records rather than a clean no-service railway
inventory. They must not be placed in exclusions automatically. A future
physical-station audit should classify each extant no-service station and test
its Rejseplanen ID in both board directions; an empty board is valid evidence
of no current service, not evidence that the station was removed.

The current work found no confirmed conventional-rail provider omission in
the cached feed. Any physically extant station on a railway not represented by
Rejseplanen must be reported as a named new-provider gap rather than assigned a
guessed `86...` ID.

## Attribution and provider constraints

- Stations: official Rejseplanen Labs GTFS Schedule/Static feed.
- Live boards: Rejseplanen API 2.0.
- Attribution: Source: Rejseplanen Labs.
- Constraint: Labs approval and an access key are required. Observe the applicable non-commercial or commercial API quota.


## Other providers

Rejseplanen covers conventional rail and Letbane, so no new heavy-rail provider is required. Metro is a later bounded mode decision.
