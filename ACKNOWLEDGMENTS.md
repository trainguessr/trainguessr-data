# Data acknowledgments

This is the canonical acknowledgment ledger for TrainGuessr station datasets
and live timetable providers. TrainGuessr reformats provider data and is not
affiliated with or endorsed by the named operators or data publishers. Names,
logos, and trademarks remain the property of their respective owners.

The generated station database is distributed under the repository's ODbL
license, subject to the source-specific terms below. API responses and source
archives remain subject to their publishers' licenses and access terms.

## Austria

- Stations: ÖBB-Infrastruktur GeoNetz and the national MVO stop dataset.
- Live boards: ÖBB SCOTTY.
- Attribution: `Datenquelle: ÖBB-Infrastruktur AG` for GeoNetz data, under CC BY 3.0 Austria.
- Constraint: obtain authorization for public use of the consumer SCOTTY endpoint or migrate to an authorized API product.

## Belgium

- Stations: Infrabel operational points, published under CC0.
- Live boards: community-run [iRail](https://api.irail.be/).
- Constraint: confirm the license for returned live railway data before public publication.

## Denmark

- Stations: official Rejseplanen Labs GTFS Schedule/Static feed.
- Live boards: Rejseplanen API 2.0.
- Attribution: Source: Rejseplanen Labs.
- Constraint: Labs approval and an access key are required. Observe the applicable non-commercial or commercial API quota.

## Finland

- Stations and live boards: [Fintraffic Digitraffic](https://www.digitraffic.fi/en/railway-traffic/).
- Attribution: Source: Fintraffic / digitraffic.fi, CC BY 4.0, with source, license, and modification notice.

## France

- Stations: SNCF Gares & Connexions `gares-de-voyageurs`, with a reviewed Cuneo-Ventimiglia supplement.
- Live boards: SNCF API / Navitia; reviewed border stations may fall back to RFI boards.
- Attribution: Source: SNCF Gares & Connexions Open Data. Station data is ODbL.
- Constraint: retain ODbL attribution/share-alike and confirm current SNCF API and underlying coverage terms.

## Germany

- Stations: Deutsche Bahn open data via `db-stations`.
- Live boards: official Deutsche Bahn Timetables API.
- Attribution: Source: Deutsche Bahn AG, CC BY 4.0, including `db-stations` notices.
- Constraint: use an API subscription and observe published request limits.

## Italy

- RFI stations and live boards: reviewed RFI records and consumer station boards.
- Ferrovienord stations and live boards: reviewed Ferrovienord records and Trenord/ViaggiaTreno.
- FSE stations and live boards: OpenStreetMap coordinates, reviewed records, and ViaggiaTreno.
- Trentino Trasporti: official GTFS under CC BY 2.5 plus reviewed legacy IDs; its legacy live source is disabled by default.
- FER and EAV: reviewed provider records and consumer station boards.
- Constraint: the undocumented or consumer live endpoints and most provider-derived station catalogues require written permission before public publication. Preserve OSM/ODbL obligations where applicable.

## Netherlands

- Stations: [Rijden de Treinen open station data](https://www.rijdendetreinen.nl/en/open-data/stations), CC0.
- Live boards: Rijden de Treinen consumer endpoint.
- Constraint: obtain permission for the undocumented live endpoint or migrate to an authorized API.

## Norway

- Stations: Entur National Stop Register.
- Live boards: Entur Journey Planner.
- Attribution: Data made available by Entur under NLOD.
- Constraint: identify requests with `ET-Client-Name` and retain Entur attribution.

## Spain

- Stations and static timetables: official Renfe GTFS feeds.
- Live updates: official Renfe GTFS-Realtime trip updates.
- Attribution: `Origen de los datos: Renfe Operadora`, with source and update metadata required by the portal reuse terms.
- Constraint: do not imply Renfe endorsement and review the portal terms before public publication.

## Sweden

- Stations: Trafiklab Stops data.
- Live boards: Trafiklab ResRobot.
- License: CC0 1.0 for the documented datasets.
- Constraint: use registered account keys, observe quotas, and do not imply Trafiklab or Samtrafiken endorsement.

## Switzerland

- Stations: opentransportdata.swiss / SBB stop data.
- Live boards: search.ch timetable API.
- Attribution: cite opentransportdata.swiss and keep published station data current.
- Constraint: confirm public-product use with search.ch or migrate to an authorized opentransportdata.swiss API.

## United Kingdom

- Stations: `davwheat/uk-railway-stations`, Trainline EU, and upstream contributors under ODbL.
- Live boards: National Rail Darwin when configured, otherwise Huxley2 as an independent proxy.
- Attribution: Source: National Rail Darwin for live railway information; preserve the station-data attribution chain and ODbL share-alike.
- Constraint: public use requires the deployer's own Rail Data Marketplace subscription and accepted terms. Do not rely on the public Huxley2 demo for production.

## General map data

- Map data: OpenStreetMap contributors, ODbL.
- Railway map data: OpenRailwayMap contributors, based on OpenStreetMap data.

Detailed generator inputs and review notes are maintained under `sources/`,
`excludes/`, `overrides/`, and `audits/` in this repository.
