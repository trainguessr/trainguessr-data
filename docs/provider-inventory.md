# TrainGuessr provider inventory

This is the cross-country inventory of every provider currently registered in
`trainguessr/src/countries/registry.py`. It also records mode boundaries and
provider gaps so that a physical station is never assigned to an unrelated
timetable namespace.

## Registered providers

| Country | Category | Runtime provider | Station/source generator | Coverage and gap status |
| --- | --- | --- | --- | --- |
| Austria | `austria_oebb` | ÖBB SCOTTY | `gen/austria.py` using GeoNetz and MVO | 1,416 nodes; `docs/review/austria-dataset-coverage.json` identifies 55 physical provider gaps across 12 named systems. |
| Belgium | `belgium_all` | iRail/NMBS-SNCB | `gen/belgium.py`; Infrabel cross-check | 603 nodes; no confirmed mainstream iRail omission. Twenty heritage stations require five named operator-specific providers; urban metro/tram is separate. |
| Denmark | `denmark_all` | Rejseplanen GTFS/API 2.0 | `gen/denmark.py` | 631 nodes, including 173 current Letbane stop IDs. Current provider/operator services are listed in `docs/denmark.md`; 44 metro stops are deferred to a later mode phase. |
| Finland | `finland_all` | Fintraffic Digitraffic | `gen/finland.py` and `docs/review/finland-reconciliation.json` | 222 nodes, including 13 no-current-traffic station sites. The audit has 262 official operational/non-passenger outcomes and 24 explicit unresolved possible-former-passenger sites; Helsinki metro/tram requires HSL or another separate provider. |
| France | `france_sncf` | SNCF API/Navitia-compatible station namespace | `gen/france.py`; `gen/france.py --audit` | 2,846 nodes from the current 2,782-record SNCF export, 52 exact current SNCF Reseau passenger supplements (including one corrected Fontanil UIC), nine exact-UIC historical passenger supplements, and six reviewed Cuneo-Ventimiglia supplements, after three explicit API-identity exclusions. The physical audit lists 20 deferred RATP/RER records, six separate-provider candidates, one Monaco scope gap, and seven unresolved SNCF/Occitanie candidates. Corsica CFC is a separate 65-stop `new_provider_needed` system. |
| Germany | `germany_all` | Deutsche Bahn Timetables/bahnhof boards | `gen/germany.py` and `docs/review/germany-reconciliation.json` | 6,652 nodes: 5,388 cached DB records, 33 AKN supplements, and 1,231 current-provider DB EVA additions. The audit lists 7 explicit current-provider gaps, 54 separate-system candidate records, and 40 stale catalogue IDs for lifecycle review; U-Bahn/tram is separate. |
| Italy | `italy_rfi` | Rete Ferroviaria Italiana / ViaggiaTreno | `gen/italy.py generate rfi` | 2,426 nodes from 2,438 source rows; six French cross-border boards use `france_sncf`, and six records are excluded. |
| Italy | `italy_fn` | Ferrovienord / Trenord | `gen/italy.py generate fn` | 111 nodes from 117 source rows; six explicit exclusions. |
| Italy | `italy_fse` | Ferrovie del Sud Est / ViaggiaTreno | `gen/italy.py generate fse` | 92 nodes from 95 source rows: 85 automatic matches, seven manual records including disused Gallipoli Porto, and three explicit non-FSE/duplicate exclusions. |
| Italy | `italy_tt` | Trentino Trasporti / legacy TrainView | `gen/italy.py generate tt` | 38 matched legacy records; runtime is disabled because the historical live endpoint is unavailable. |
| Italy | `italy_fer` | Ferrovie Emilia Romagna / PittiInfo | `gen/italy.py generate fer` | 119 nodes from 132 source rows; 13 explicit exclusions and guarded reviewed coordinates, including `S05100`. |
| Italy | `italy_eav` | Ente Autonomo Volturno | `gen/italy.py generate eav` | 119 nodes from 126 source rows; seven explicit exclusions. |
| Netherlands | `netherlands_all` | Rijden de Treinen / NS and other Dutch operators | `gen/netherlands.py` | 397 nodes. Rijden de Treinen describes its NL catalogue as all Dutch railway stations, sourced directly from NS and refreshed for station openings, closures, and renames. The data includes two `facultatiefStation` records. Metro/tram is separate. |
| Norway | `norway_all` | Entur Journey Planner / National Stop Register | `gen/norway.py` | 367 active rail nodes. Entur requires stops in use to be ACTIVE and publishes nightly current, future, and all-version/outdated NeTEx dumps with stable NSR IDs. The generator excludes INACTIVE records pending historical and physical review. Metro/tram is deferred. |
| Spain | `spain_renfe` | Renfe official GTFS and GTFS-Realtime | `gen/spain.py` | 1,465 tracked nodes. Explicit provider-native stations are included even when no current trip serves them. Renfe's complete-stations catalogue is an authoritative cross-check, but its CSV download is unavailable from the portal archiver. |
| Spain | `spain_fgc` | FGC official GTFS and GTFS-Realtime | `gen/spain.py --skip-renfe --fgc <feed> --no-download` | 91 rail nodes from the 2026-08-26 official feed; 14 rail routes and 6,526 rail trips. Metro, funicular, rack, and replacement-bus routes are deferred. |
| Sweden | `sweden_all` | Trafiklab ResRobot | `gen/sweden.py` | 839 nodes: 739 rail and 100 metro. Trafiklab’s national stop data/ResRobot covers all Swedish operators, uses the same national `740...` stop IDs as GTFS Sverige 2, and refreshes when source data changes. The generator has no current-trip gate. Ordinary tram expansion is out of scope; the existing provider covers metro. |
| Switzerland | `switzerland_all` | Search.ch stationboard / Swiss Transport API | `gen/switzerland.py` | 1,697 current `TRAIN` service-point nodes. Swiss service-point v2 also publishes full past/future validity records; the generator reads current service points and filters `meansoftransport=TRAIN`. Non-TRAIN and historical records need proof of a physical passenger station addressable by search.ch. |
| United Kingdom | `uk_national_rail` | National Rail Darwin, with Huxley2 fallback | `gen/uk.py` | 2,608 nodes. The upstream catalogue contains 2,608 stations queryable through National Rail Darwin, including Cambridge South (`CMS`) and Beaulieu Park (`BPA`). Northern Ireland Railways and heritage/private systems are future-provider entries; metro is deferred. |

## Named new-provider backlog

These systems were discovered as physically relevant but are not assigned a
foreign or unrelated provider ID.

| System | Country | Stations/status |
| --- | --- | --- |
| SDP / Stoomtrein Dendermonde-Puurs | Belgium | 5 extant tourist-rail stations; no iRail identity. |
| CFV3V | Belgium | 4 extant tourist-rail stations; no iRail identity. |
| PFT/TSP | Belgium | 6 extant tourist-rail stations; no iRail identity. |
| Stoomtrein Maldegem-Eeklo / Stoomcentrum Maldegem | Belgium | 2 extant tourist-rail stations; no iRail identity. |
| Rail Rebecq Rognon | Belgium | 3 extant tourist-rail stations; no iRail identity. |
| MVO-only/private Austrian systems | Austria | 55 physical provider-gap stations across 12 named systems; see `docs/review/austria-dataset-coverage.json`. |
| Chemins de fer de la Corse (CFC) | France | Official CFC pages report 16 stations and 49 halts with current PDF schedules, but no stable native stop namespace/API was found; 65 passenger stops require a new provider. Do not assign SNCF IDs. |
| SSIF, AMT, STA, Infrastrutture Venete, Rete Ferroviaria Toscana, ASTRAL, Ferrovia Adriatico Sangritana, Ferrovie del Gargano, Ferrotramviaria, Ferrovie Appulo Lucane, Ferrovie della Calabria, ARST, Ferrovia Circumetnea | Italy | Named candidate systems from the country handoff; each requires stable native IDs and a usable timetable source before implementation. |
| FGC, Euskotren, and other regional/non-Renfe rail | Spain | Requires separate official provider research; never assign Renfe IDs. |
| Mansfelder Bergwerksbahn and tourist/heritage rail | Germany | 10 current GTFS candidates require a separate provider identity; see `docs/review/germany-reconciliation.json`. |

Urban mode boundaries are provider-specific. Current providers that already
support an urban rail mode are extended in their own namespace when the source
is verified: Denmark Letbane is included in `denmark_all`, and Sweden already
includes metro. Supported but deferred modes are documented here rather than
written to exclusions: Denmark metro, Swedish tram, Helsinki metro/tram, and
the urban systems of countries whose current provider has not been validated
for that mode.

## Reporting format

Country completion records should report, at minimum:

- `N` stations from `<provider/system>` require a new provider;
- `M` stations are completely missing and require `<provider/system>`;
- `K` stations were added to an existing provider after native-ID validation;
- `L` stations were already represented or included;
- `R` stations were excluded because physical infrastructure is dismantled;
- urban stations supported by the current provider were added immediately,
  while stations requiring a different provider were named explicitly.

No guessed provider IDs are acceptable in any of these counts.
