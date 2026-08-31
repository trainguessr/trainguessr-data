# New-provider candidates

## Purpose

List each provider or scope gap with its official sources, native-ID proof,
runtime leads, scope, and build tasks. A
physical match is not a provider ID.

### Provider acceptance checklist
Before building any candidate below, check all of the following:

1. official/native station namespace exists and is stable;
2. physical passenger-station set can be built, including existing
   no-current-service stations;
3. current timetable/departure/arrival behavior works for TrainGuessr;
4. scheduled-only data is clearly labeled separately from realtime data;
5. the meaning of empty boards and temporarily interrupted service is clear;
6. licensing/attribution allows repository/runtime use;
7. station IDs are never invented from OSM, names, coordinates, nearby stops,
   or an unrelated provider;
8. the same generator input gives the same output;
9. runtime code can be tested with stable fixtures or standards-based adapters;
10. a station is not counted as covered just because its name appears as an
    intermediate calling point in some other provider's train.

## France

### Chemins de fer de la Corse (CFC)

CFC requires a separate provider; do not put its stations in `france_sncf`.

Facts:
- CFC's official site describes 16 stations and 49 halts, i.e. 65 named
  passenger stopping places.
- Current passenger service is published by CFC through operator timetable
  pages/PDFs.
- The French national transport access point has an official Collectivité de
  Corse GTFS archive for CFC. A resource published 2026-03-04 was valid only
  2026-03-03 through 2026-03-09 and is now marked stale. The archive supplies a
  native GTFS namespace instead of guessed identifiers.
- That GTFS resource reports 6 routes, 147 stop points and 120 stop areas and is
  licensed under Licence Ouverte 2.0.

Sources:
- https://cf-corse.corsica/les-gares/
- https://cf-corse.corsica/plan-du-reseau/
- https://cf-corse.corsica/horaires/
- https://transport.data.gouv.fr/datasets/gtfs-transport-horaires-chemins-de-fer-corse-1
- https://transport.data.gouv.fr/redocs/83882
- existing repository notes: `docs/france.md`,
  `docs/review/france-reconciliation.json`

Next actions:
- download the most recent and historical CFC GTFS resources and check
  whether stop IDs are stable between snapshots;
- separate stop areas from platforms/quays and build the 65 physical
  passenger sites deterministically;
- find a current machine-readable timetable or realtime source; do not treat
  a stale one-week GTFS snapshot as current runtime proof;
- if only current PDFs exist, document the provider gap rather than make up a
  pseudo-provider;
- check Ajaccio and the complete network.

### Chemins de fer de Provence

- the 95-UIC reconciliation identifies at least two physical candidates
  outside SNCF;
- exact candidates and OSM evidence are in
  `docs/review/france-reconciliation.json`.

Next actions:
- find the operator/region's official station list and native IDs;
- find a current timetable/realtime source for the Nice–Digne railway;
- check whether any national/regional open-data GTFS/NeTEx feed already
  lists the complete line;
- do not assign SNCF UICs unless the SNCF runtime actually accepts the exact
  station.

### TTDA

- one France physical-audit candidate is listed outside SNCF.
- see `docs/review/france-reconciliation.json`.

Next actions:
- find the exact operator/system expansion behind the recorded candidate;
- check whether regular public passenger timetables and stable station IDs
  exist;
- ordinary museum/event operation is not a heavy-rail completion gate under the
  current scope, but keep the candidate here.

### ATTCV

- one France physical-audit candidate is listed outside SNCF.
- see `docs/review/france-reconciliation.json`.

Next actions:
- get the exact candidate/station from the reconciliation ledger;
- check operator timetable publication and native station namespace;
- keep in the backlog if service is purely tourist/event based.

### CFHA

- one France physical-audit candidate is listed outside SNCF.
- see `docs/review/france-reconciliation.json`.

Next actions:
- get the exact candidate/station from the reconciliation ledger;
- check whether a stable machine-readable timetable namespace exists;
- label the provider as heritage scope if service is tourist/event-only.

### Monaco rail scope/provider gap

Monaco is a provider/scope gap. Historical UIC evidence is not enough to add it
to SNCF automatically; require an exact runtime-provider and country-scope
decision. Do not assume Monaco coverage from nearby French SNCF
stations.

## Austria

The following Austrian physical systems or station groups lack a confirmed
native SCOTTY railway identity. Detailed station names, coordinates, and
reasons are machine-readable in
`docs/review/austria-dataset-coverage.json`.

### Gailtalbahn

Reisach is a physical railway halt, but nearby MVO
`at:42:6171` is bus-only and OSM `uic_ref=8101434` was not accepted by
SCOTTY. Do not substitute the locality/bus stop.

Next action: find the current operator/timetable namespace and exact Reisach
station identity.

### ÖGLB

Payerbach Lokalbahn: Current SCOTTY shows the nearby mainline
station but no exact Lokalbahn railway identity.

### NÖVOG and regional narrow-gauge railways

Unresolved physical stations include Haag-Kleinsierning and
St. Margarethen - Rammersdorf. Before creating anything new, re-test whether
current NÖVOG/Mobilitätsverbünde/SCOTTY data now has stable rail-specific
IDs.

### Zayatalbahn / Leiser Berge railway

Physical stations: Ernstbrunn, Ernstbrunn-Thomasl, Mollmannsdorf.
Existing MVO/SCOTTY results were bus/locality identities rather than confirmed
rail station identities.

### ÖGEG / Steyrtal-Museumsbahn

The Austria ledger lists multiple physical museum-railway stations,
including Steyr Lokalbahnhof, Grünburg, Neuzeug and others. SCOTTY currently
shows nearby bus/museum-area stops rather than confirmed rail-specific IDs.

### Feistritztalbahn

Physical stations include Anger, Birkfeld, Koglhof and Rosegg. No exact
current SCOTTY railway identities were confirmed.

### Stainzerbahn (PWS)

Physical stations are recorded in
`docs/review/austria-dataset-coverage.json`. Find an operator-native namespace
before building the provider.

### Breitenauer Bahn (MStE)

Physical stations include Breitenau and St. Jakob-Breitenau.

### Erzbergbahn (VE)

Physical stations include Erzberg and Präbichl. Check current passenger/tourist
service behavior and stable station IDs before building the provider.

### Bregenzerwaldbahn / VBM

Physical stations include Bezau, Reuthe and Schwarzenberg. The Austria
ledger also groups some records with Rheinschauen; treat the systems as
separate providers.

### Rheinschauen railway

Get the exact physical candidate records from
`docs/review/austria-dataset-coverage.json`. Under the current scope this is likely
a heritage backlog rather than a completion gate.

### Burgenland Draisine route

Physical former railway stops are recorded for Neckenmarkt-Horitschon,
Lackenbach, Markt St. Martin, Oberpullendorf, Raiding-Lackendorf, Stoob,
Weppersdorf-Kobersdorf and Draßmarkt-Neutal. Current SCOTTY identities are
bus/locality records. A draisine operation is not a required TrainGuessr heavy
rail provider under the present scope.

### Rosentaler Museumsbahn

Physical stops include Ferlach and Historama; current SCOTTY results were
bus identities.

### Taurachbahn

Use the exact station list and evidence recorded in
`docs/review/austria-dataset-coverage.json` when building the provider.

### Other Austrian regional records

The Austria ledger also has composite records involving Salzburg AG, ÖBB,
Gailtalbahn and other regional physical features (for example Wildshut Gut
Wildshut and Langkampfen). These are **not automatically new providers**.
Before opening a provider project, check exact stations in SCOTTY and the native
namespace again, then separate bad crosswalks from unsupported systems.

## Belgium

These five systems account for the 20 explicitly reviewed physical Belgian
tourist-rail stations that have no iRail/NMBS identity. Exact station names and
coordinates are in `docs/belgium.md`.

### Stoomtrein Dendermonde-Puurs (SDP)

Five reviewed stations: Baasrode-Noord, Buggenhout a/d Schelde, Sint-Amands, Oppuurs,
Sint-Pietersburcht.

Baasrode-Noord is an important lifecycle example: stale/abandoned OSM tagging
must not override evidence that the station and tourist railway are in use.

### CFV3V

Four reviewed stations: Nismes, Olloy-sur-Viroin, Vierves, Treignes.

### PFT/TSP

Six reviewed stations: Braibant, Dorinne-Durnal, Évrehailles, Purnode, Senenne,
Spontin.

### Stoomtrein Maldegem-Eeklo / Stoomcentrum Maldegem

Two reviewed stations: Balgerhoeke and Maldegem.

### Rail Rebecq Rognon

Three reviewed stations: Bloc U, Rebecq, Rognon.

For all five Belgian systems: do not attempt to reuse iRail IDs unless the
exact station appears in the iRail namespace. Under the current project scope
heritage-only providers are backlog, not a heavy-rail completion
gate.

## Germany

The GTFS check has 54 records labeled `new_provider_needed`;
these are mostly heritage/tourist/park-rail systems rather than missing
DB regional rail. Exact records live in
`docs/review/germany-reconciliation.json`.

### Verkehrsbetriebe Grafschaft Hoya / heritage services

The ledger has 16 GTFS records. Examples include Hoya(Weser), Hassel(Weser),
Bruchhausen-Vilsen and Syke-area
heritage stations. Get the route 403 records from the reconciliation ledger.

### Mansfelder Bergwerksbahn

Six GTFS records include Zirkelschacht, Hettstedt Kupferkammerhütte, Eduardschacht,
Siersleben (Bergwerksbahn), Bocksthal.

### Selfkantbahn

Five GTFS records use the agency `AVV Handeingabe`; examples include Birgden,
Gillrath and Schierwaldenrath. Do not mistake the transport-association feed
identity for a DB EVA namespace.

### Museums-/tourist railway records in MittelSachsen

Five GTFS records include Schweizerthal-Diethensdorf, Neuschweizerthal,
Markersdorf-Taura, Amselgrund and Markersdorf Alte Mühle / Schreckenstein.
Find the actual railway/operator before any provider design; the GTFS
agency label `MittelSachsen` is an aggregator label, not necessarily the
operator.

### Kleinbahn Magdeburgerforth

Four GTFS records include Magdeburgerforth Lumpenbahnhof, Lindenstr., Mitte and the
main Kleinbahn stop.

### Waldeisenbahn / Weißwasser-Kromlau-Bad Muskau group

Nine GTFS records grouped under ZVON include Feuerturmteich, Gablenz/Gora,
Weißwasser Teichstraße, Weißwasser Ost,
Kromlau Waldeisenbahn, Bad Muskau, Schwerer Berg and Baierweiche. Find the
actual operator namespace instead of using the regional association label as a
provider.

### Prien Hafen / non-federal railway record

The single GTFS record uses the generic agency `Nichtbundeseigene Eisenbahnen`.
Find the real
operator and whether this station is required under the current railway scope
before building the provider.

### VRN heritage records

The two reconciliation records are Helmbach Bahnhof and Frankeneck Bahnhof.
Find the actual railway/operator behind them.

### Parkeisenbahnen

Six GTFS records include Vatterode and Bernburg park railway stops.
Park/miniature railways are
explicitly not a TrainGuessr completeness target.

## Italy

The six existing providers (`italy_rfi`, `italy_fn`, `italy_fse`, `italy_tt`,
`italy_fer`, `italy_eav`) may receive exact provider-compatible heavy-rail
stations. An RFI interchange does **not** prove RFI support for the independent
line beyond it.

### STA / Vinschgau (Merano-Malles)

Native-ID rule:
- RFI knowing Merano does not prove RFI knows the Vinschgau line.
- Exact line-only stations such as Malles, Sluderno, Lasa, Silandro and Naturno
  must be tested in the actual provider namespace.

Sources and runtime:
- NOI/Open Data Hub's South Tyrol transport stack has a dedicated STA NeTEx
  feed and connects STA SIRI Estimated Timetable and Situation Exchange feeds.
- This strongly suggests stable NeTEx StopPlace/Quay identities plus
  standards-based realtime, separate from Trenitalia/RFI.

Sources and leads:
- NOI Open Data Hub transport APIs and repositories;
- `opendatahub-mentor-otp` build configuration (`sta` NeTEx feed);
- Open Data Hub GTFS API/repository;
- STA/Open Data Hub SIRI Estimated Timetable and Situation Exchange endpoints.

Next actions:
- download current STA NeTEx;
- list only railway StopPlaces/Quays for Merano-Malles and any other
  STA-operated conventional railway in scope;
- map SIRI IDs to NeTEx IDs;
- test departure/estimated timetable behavior, including empty boards and
  interrupted service;
- consider a reusable NeTEx/SIRI adapter only after the exact schema is proven.

### SSIF / Vigezzina-Centovalli

The existing Swiss/search.ch backend may support this system.

Runtime lead:
- current search.ch/opentransportdata timetable results show Italian SSIF
  stations such as Re, Malesco, S. Maria Maggiore, Druogno, Trontano and
  Masera, including current train information.
- First test the existing
  `switzerland_all` runtime namespace against exact Italian SSIF stations
  before designing an SSIF-specific backend.

Next actions:
- find exact search.ch/opentransportdata station IDs for every Italian
  SSIF station;
- test existing TrainGuessr Swiss provider code with those IDs;
- keep country/category organization separate from backend reuse;
- use SSIF official timetables/station pages for physical completeness;
- do not manufacture IDs from station names.

### AMT Genova-Casella

Sources:
- AMT officially publishes GTFS open data.
- AMT journey-planning data has stable Genova-Casella station identifiers
  in the `GC01` through `GC18` range.
- AMT states that its passenger systems/app give live arrival information
  for the railway.

Source:
- https://www.amt.genova.it/amt/societa_trasparente/altri-contenuti/open-data/

Next actions:
- archive current GTFS and select only the Genova-Casella railway;
- check the full `GC01..GC18` station hierarchy;
- check AMT website/app HTTP requests to find the realtime arrivals
  endpoint and station-key relationship;
- keep railway stations during temporary bus substitution;
- build the provider only after runtime behavior and licensing are confirmed.

### Ferrovie Appulo Lucane (FAL)

Sources and leads:
- FAL has an official realtime bus/train passenger page.
- Regione Puglia/ASSET publishes railway Programma di Esercizio data useful
  as an official static cross-check.
- Regional mobility systems may have GTFS/NeTEx/SIRI data; check rather
  than assuming.

Next actions:
- get the official railway station set and native numeric IDs;
- map the official realtime page/backend requests;
- check whether IDs are stable across timetable cycles;
- separate FAL buses from railway;
- check Regione Puglia MaaS/RAP feeds for standards-based data.

### Ferrovie del Gargano

Sources and leads:
- the official operator website has an arrivals/departures system and
  internal station values such as `APRICENA`, `CAGNANO`, `CARPINO1`;
- Regione Puglia/ASSET publishes FDG railway Programma di Esercizio data.

Next actions:
- check the live board's exact HTTP requests/server endpoints;
- list the full railway station key set;
- cross-check against Puglia railway data and physical station evidence;
- check whether station keys are stable enough to use as TrainGuessr IDs.

### Ferrotramviaria / Ferrovie Nord Barese

Sources and leads:
- operator documentation states that website/app realtime train-running
  information is available;
- Regione Puglia/ASSET publishes FNB/Ferrotramviaria railway Programma di
  Esercizio data;
- an older official GTFS trail exists but must not be treated as current if its
  service dates are expired.

Next actions:
- check the current live train-running backend;
- find stable station IDs;
- find a current official GTFS/NeTEx feed if available;
- use regional Puglia railway data for completeness, not as a runtime ID unless
  the live backend shares it.

### Ferrovia Circumetnea (FCE) — conventional railway

Official data:
- FCE publishes its current scheduled service as GTFS.
- The currently published package is valid 2025-02-01 through 2028-02-28,
  created/updated 2026-02-13.
- It contains the standard GTFS station/route/trip/stop-time files plus FCE
  extension tables.

Sources:
- https://www.circumetnea.it/pubblicazione-orari-del-trasporto-pubblico-locale-in-formato-gtfs/
- https://www.circumetnea.it/download/general-transit-feed-specification-fce-01-02-2025-28-02-2028/

Scope:
- conventional Paternò-Riposto/Circumetnea railway: heavy-rail/narrow-gauge
  backlog;
- Catania metro: later metro phase;
- bus routes: out of rail scope.

Next actions:
- build the conventional-rail station ID list deterministically from current GTFS;
- check existing no-current-service railway stations separately;
- check FCE app/web realtime;
- if no realtime exists, decide project-wide whether a standards-based
  scheduled-GTFS runtime provider is acceptable before making a custom FCE
  class.

### ARST railway

Official data:
- Regione Sardegna publishes ARST GTFS under its mobility open-data portal;
- current metadata lists validity from 2026-01-01 through 2026-12-31 and last
  modified 2026-08-27.

Source:
- https://www.sardegnamobilita.it/open-data/arst

Scope:
- conventional/narrow-gauge railway: heavy-rail backlog;
- metrotranvia: later bounded metro/light-rail phase;
- bus: exclude;
- tourist railway: document as a separate provider gap unless
  it operates as normal public passenger railway.

Next actions:
- separate railway routes/trips/stops from the multimodal ARST GTFS;
- find stable station IDs;
- check the ARST journey-planner/realtime backend;
- check inactive but existing railway stations against the feed.

### Ferrovie della Calabria

Sources and leads:
- Regione Calabria publishes a regional GTFS at
  `https://mobilita.regione.calabria.it/gtfs/otp_gtfs.zip`;
- the feed includes Ferrovie della Calabria among regional operators and was
  refreshed in August 2026;
- FdC's official site publishes current railway timetables/journey information.

Next actions:
- separate FdC railway routes/stations from the regional multimodal feed;
- find stable station IDs and check timetable validity;
- check FdC's journey/ticket/app backend for realtime;
- include existing stations on interrupted sections even when no
  current trip serves them.

### Rete Ferroviaria Toscana / Trasporto Ferroviario Toscano (TFT)

Source:
- Regione Toscana publishes a dedicated `TFT.gtfs` for Arezzo-Stia and
  Arezzo-Sinalunga;
- the resource was updated in June 2026 under CC Attribution.

Next actions:
- archive current TFT GTFS and find stable stop IDs;
- check all physical passenger stations on both lines, including no-current
  service;
- check TFT passenger information for realtime;
- if no realtime source exists, apply the future project-wide scheduled-GTFS
  provider policy instead of writing a one-off scraper.

### Infrastrutture Venete

Important rule:
- RFI can address Adria and RFI boards can show Infrastrutture Venete stations
  as intermediate calls, but this does **not** prove that every IV station has
  an addressable RFI `placeId`.
- Do not repeat the Merano inference error.

Next actions:
- list every physical passenger station on the IV lines;
- for each station test exact RFI station lookup/board identity;
- put exact RFI-covered stations in `italy_rfi`;
- consider a new provider only for exact stations without RFI runtime
  identities;
- use Infrastrutture Venete/Trenitalia service information as supporting
  evidence, not a provider-ID substitute.

### Ferrovia Adriatico Sangritana / TUA

Provider-ID rule:
- TUA trains running on RFI infrastructure do not prove RFI provider coverage
  for stations on TUA-owned infrastructure;
- temporary interruption of traffic on TUA infrastructure does not remove
  physical passenger stations.

Runtime lead:
- TUA passenger digitization uses/has used Pysae technology; Pysae documents
  GTFS-Realtime and SIRI support. Public access to TUA-specific
  feeds still needs proof.

Next actions:
- list TUA-owned passenger infrastructure separately from TUA services on
  RFI;
- search TUA/Regione Abruzzo/Pysae for GTFS, GTFS-RT, NeTEx or SIRI;
- test exact RFI IDs only for stations actually addressable by RFI;
- keep interrupted physical stations.

### ASTRAL / Lazio regional rail systems

Scope:
- Metromare: metro-like; later metro phase.
- Roma-Civita Castellana-Viterbo: check later under the bounded
  railway-like light-rail/regional-rail rule.
- ordinary Rome tram: out of completeness scope.

Keep ASTRAL realtime/infomobility leads for the later mode pass; do not expand
the present heavy-rail audit into Rome urban transit.

## Spain

### Ferrocarrils de la Generalitat de Catalunya (FGC)

FGC has 91 generated, physically reconciled rail stations and is not part of
`spain_renfe`. Add the timetable provider to the default public-ready set only
after a successful live smoke test.

Official data:
- FGC has an official open-data portal;
- FGC explicitly publishes static GTFS and realtime GTFS-RT-style data;
- its network includes Barcelona-Vallès, Llobregat-Anoia, Lleida-La Pobla and
  rack/mountain services. The provider selects GTFS rail route types and
  defers metro, funicular, rack, bus, and replacement-bus route types.

Sources:
- https://dadesobertes.fgc.cat/
- https://dadesobertes.fgc.cat/explore/assets/gtfs_zip/api/
- https://www.fgc.cat/en/fgc-faq/how-can-the-technical-journey-data-such-as-json-files-available-on-the-open-data-portal-be-interpreted/

Build notes:
- `gen/countries/spain/fgc.py` copies official GTFS station IDs and builds
  `cache/spain-fgc.sqlite`;
- `countries.spain.fgc` serves scheduled boards with an optional official
  GTFS-RT overlay and rejects expired static feeds;
- the generated node file and physical evidence are in
  `nodes/nodes-spain-fgc.json` and `docs/review/spain-fgc-reconciliation.md`;
- FGC uses a namespace independent of `spain_renfe`.

### Euskotren

Official data:
- Open Data Euskadi's Moveuskadi dataset publishes multimodal GTFS, GTFS-RT,
  SIRI and NeTEx indexes and includes autonomous railways;
- the dataset was updated 2026-08-29 with realtime update frequency.

Source:
- https://opendata.euskadi.eus/catalogo/-/moveuskadi-datos-de-la-red-de-transporte-publico-de-euskadi-operadores-horarios-paradas-calendario-tarifas-etc/

Next actions:
- select Euskotren heavy-rail routes only;
- separate Metro Bilbao/tram/funicular and other modes;
- check whether operator-native IDs or Moveuskadi NeTEx/GTFS IDs should be the
  main IDs;
- check GTFS-RT/SIRI station linkage.

### Other non-Renfe Spanish regional/narrow-gauge rail

The current `spain_renfe` provider cannot receive guessed IDs for a
non-Renfe system. Document each additional operator/system requiring its own
namespace with official sources and exact station counts.

## United Kingdom

### Northern Ireland Railways / Translink

Provider-ID rule:
- `uk_national_rail` is a National Rail CRS/Darwin provider and does not
  automatically cover Northern Ireland Railways.
- OpenDataNI publishes NIR rail timetable CIF data.

Official data:
- NIR Rail CIF dataset updated 2026-04-16 and published under the UK Open
  Government Licence; dataset page updated 2026-04-22.
- extra location-conversion data is published alongside it.

Source:
- https://www.data.gov.uk/dataset/e41b1057-b0bd-4419-95eb-77057c8ad6b0/translink-northern-ireland-rail-timetable

Next actions:
- list all NIR passenger stations and their stable CIF/location codes;
- check the Translink live journey/board backend for current departures/realtime;
- keep this provider separate from National Rail unless exact Darwin support is
  proven.

### Heritage/private UK railways

Heritage/private railways are outside National Rail. Record only railway-like
public passenger systems that require separate
station/timetable identities. Ordinary heritage/event rail is not a completion
requirement.

### London Underground / Glasgow Subway / Tyne and Wear Metro

Evaluate these during the metro phase, not the heavy-rail audit. Add precise
source/runtime notes when discovered.

### UK tram systems

These are out of scope unless a specific system satisfies the project's strict
train-like light-rail boundary. Ordinary tram completeness is not required.

## Other mode/provider scope

The following are outside new-provider work during the heavy-rail phase:

- Helsinki metro: likely HSL namespace; later metro phase.
- Denmark metro: first test existing Rejseplanen provider, so this may not need a
  new provider.
- Netherlands metro: later metro phase.
- Norway metro: first test Entur's existing namespace/runtime; may not need a
  new provider.
- Sweden metro is already supported by the existing provider.
- German U-Bahn systems: later metro phase.
- ASTRAL Metromare and similar metro-like systems: later metro phase.
- ordinary tram systems in every country: listed only, not a project
  completion requirement.

## Build workflow

1. read the relevant country's `docs/<country>.md`;
2. read the machine-readable reconciliation/source ledger referenced in that
   section;
3. refresh the official source URL and record its date/version/hash;
4. prove exact native station IDs on representative active, empty-board,
   interrupted-service and interchange stations;
5. prefer reusable standards adapters (GTFS/GTFS-RT, NeTEx/SIRI) where several
   providers genuinely share behavior, but do not force unlike backends into a
   false abstraction;
6. add provider runtime code, generator integration, fixtures and tests as one
   provider build;
7. update this file by moving built providers into the per-country
   documentation rather than leaving stale backlog prose behind.
