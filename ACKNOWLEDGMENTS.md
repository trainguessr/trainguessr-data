# Data acknowledgments

This repository reformats provider data and is not affiliated with or endorsed by
the named operators or data publishers. Their owners hold all rights to names,
logos, and trademarks.

The curated station dataset is offered under ODbL 1.0 **only where the
upstream rights allow redistribution**; see [LICENSE](LICENSE) and the
per-category [publication status](docs/source-terms.json). This licence notice
cannot override third-party API access, contractual or redistribution restrictions.
Do not treat every `nodes/` file as unconditionally cleared for redistribution.
Raw source archives and live API responses retain the publishers' rights.
Trainline and derived UK station data require attribution and ODbL share-alike.

## Austria

- Stations: ÖBB-Infrastruktur GeoNetz and the national MVO stop dataset.
- Live boards: ÖBB SCOTTY.
- Attribution: `Datenquelle: ÖBB-Infrastruktur AG` for GeoNetz data, under CC BY 3.0 Austria.
- Constraint: get authorization for public use of the consumer SCOTTY endpoint or move to an authorized API product.

## Belgium

- Stations: Infrabel operational points, published under CC0.
- Live boards: community-run [iRail](https://api.irail.be/).
- Constraint: confirm the license for returned live railway data before public publication.

## Denmark

- Stations: official Rejseplanen Labs GTFS Schedule/Static feed.
- Live boards: Rejseplanen API 2.0.
- Attribution: Source: Rejseplanen Labs.
- Constraint: Labs approval and an access key are required. Follow the relevant non-commercial or commercial API quota.

## Finland

- Stations and live boards: [Fintraffic Digitraffic](https://www.digitraffic.fi/en/railway-traffic/).
- Attribution: Source: Fintraffic / digitraffic.fi, CC BY 4.0, with source, license, and modification notice.

## France

- Stations: SNCF Gares & Connexions `gares-de-voyageurs`, with a reviewed Cuneo-Ventimiglia supplement.
- Live boards: SNCF API / Navitia; reviewed border stations may fall back to RFI boards.
- Separate provider evidence: current Chemins de fer de la Corse operator schedules and network pages.
- Île-de-France secondary-mode cross-check: Île-de-France Mobilités station registry and GTFS-aligned stop dataset, under Licence Ouverte/ODbL as published by the datasets.
- Physical discovery audit: OpenStreetMap contributors through bounded Overpass captures, under ODbL.
- Attribution: Source: SNCF Gares & Connexions Open Data. Station data is ODbL.
- Constraint: follow ODbL attribution/share-alike rules and confirm current SNCF API and underlying coverage terms.

## Germany

- Stations: Deutsche Bahn open data via `db-stations`.
- Physical discovery and regional supplements: GTFS.de/DELFI GTFS feed, with the feed's DELFI e.V. and GTFS.de attribution, plus OpenStreetMap contributors through bounded Overpass captures under ODbL.
- Live boards: official Deutsche Bahn Timetables API.
- Attribution: Source: Deutsche Bahn AG, CC BY 4.0, including `db-stations` notices.
- Constraint: use an API subscription and follow published request limits.

## Italy

- RFI stations and live boards: reviewed RFI records and consumer station boards.
- Ferrovienord stations and live boards: reviewed Ferrovienord records and Trenord/ViaggiaTreno.
- FSE stations and live boards: OpenStreetMap coordinates, reviewed records, and ViaggiaTreno.
- Trentino Trasporti: official GTFS under CC BY 2.5 plus reviewed legacy IDs; its legacy live source is disabled by default.
- FER and EAV: reviewed provider records and consumer station boards.
- Constraint: the undocumented or consumer live endpoints and most provider-derived station catalogues require written permission before public publication. Follow OSM/ODbL rules where applicable.

## Netherlands

- Stations: [Rijden de Treinen open station data](https://www.rijdendetreinen.nl/en/open-data/stations), CC0.
- Live boards: Rijden de Treinen consumer endpoint.
- Constraint: get permission for the undocumented live endpoint or move to an authorized API.

## Norway

- Stations: Entur National Stop Register.
- Live boards: Entur Journey Planner.
- Attribution: Entur data under NLOD.
- Constraint: identify requests with `ET-Client-Name` and keep Entur attribution.

## Spain

- Stations and static timetables: official Renfe GTFS feeds.
- Live updates: official Renfe GTFS-Realtime trip updates.
- Attribution: `Origen de los datos: Renfe Operadora`, with source and update metadata required by the portal reuse terms.
- Constraint: do not imply Renfe endorsement and review the portal terms before public publication.

## Sweden

- Stations: Trafiklab Stops data.
- Live boards: Trafiklab ResRobot.
- License: CC0 1.0 for the documented datasets.
- Constraint: use registered account keys, follow quotas, and do not imply Trafiklab or Samtrafiken endorsement.

## Switzerland

- Stations: opentransportdata.swiss / SBB stop data.
- Live boards: search.ch timetable API.
- Attribution: cite opentransportdata.swiss and keep published station data current.
- Constraint: confirm public-product use with search.ch or move to an authorized opentransportdata.swiss API.

## United Kingdom

- Stations: `davwheat/uk-railway-stations`, Trainline EU, and upstream contributors under ODbL.
- Live boards: National Rail Darwin when configured, otherwise Huxley2 as an independent proxy.
- Attribution: Source: National Rail Darwin for live railway information; keep the station-data attribution chain and follow ODbL share-alike rules.
- Constraint: public use requires the deployer's own Rail Data Marketplace subscription and accepted terms. Do not rely on the public Huxley2 demo for production.

## General map data

- Map data: OpenStreetMap contributors, ODbL.
- Railway map data: OpenRailwayMap contributors, based on OpenStreetMap data.

## Spain: FGC

- Stations and schedules: official FGC Open Data GTFS.
- Live trip updates: official FGC GTFS-Realtime data.
- Attribution: Ferrocarrils de la Generalitat de Catalunya (FGC), CC BY 4.0.
- Source: <https://dadesobertes.fgc.cat/>.

## Italian station identifier links

- Exact ViaggiaTreno/UIC/ÖBB/DB station links: Trainline EU stations dataset and
  contributors, https://github.com/trainline-eu/stations, ODbL1.0.
- Links enrich existing reviewed RFI stations; they do not supply RFI place IDs,
  station names/coordinates or railway realtime facts. Preserve attribution and
  the applicable ODbL obligations on redistribution.
