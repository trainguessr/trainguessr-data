# Trainguessr Dataset

## How each country was obtained

### Austria

Austria has good open data, but a somewhat janky API for real time departures. The API ([here](https://fahrplan.oebb.at/bin/stboard.exe/dn)) returns JavaScript objects, which are then parsed and converted to JSON. The API is not documented, but it works well enough.

The list of stations was obtained from the ÖBB open data website: [ÖBB](https://data.oebb.at/).

### Belgium

Infrabel exports its stations as open data in a JSON file [here](https://opendata.infrabel.be/explore/dataset/operationele-punten-van-het-netwerk/export/?sort=ptcarid).

Trainguessr uses the iRail API ([here](https://docs.irail.be/#)) as it makes things way easier. Stations and live departures are obtained from the iRail API, which is a public API that does not require an API key.

### France

SCNF export its stations as open data in a JSON file [here](https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe%2FBerlin).

These station IDs are then used in the SNCF API, which requires an API key. The API key is obtained by creating a free account on the SNCF Numerique website: [SNCF Numerique](https://numerique.sncf.com/).

### Germany

The German railway system is a bit of a mess. The Deutsche Bahn API is not public, but it is possible to get the real time departures from the DB website: [DB](https://www.bahnhof.de/api/boards). The list of stations is obtained from the DB open data website: [DB Open Data](https://data.deutschebahn.com/). It thankfully uses UIC codes.

### Italy

Italy's RFI is notorious for its lack of public APIs. This website, written in pure HTML, allows someone to query data about train schedules and routes: [RFI](https://www.rfi.it/it/stazioni/pagine-stazioni/servizi-di-qualita/informazioni-al-pubblico/monitor-arrivi-partenze-live.html).

The website embeds the train information along with the logos as base64 images and has a very good CSS. This CSS was fetched and modified to fit TrainGuessr. On the other hand, the whole HTML page is fetched, the timetable obtained and inserted as-is in the page.

The RFI IDs are the same as the TrainGuessr IDs. To match them to the geolocation data, a lot of manual labor and scripting was done.

All non-RFI stations (at the time of writing: Ferrovie Nord, Trentino Trasporti, Ferrovie Emilia Romagna, Ente Autonomo Volturno) each have their own API. In particular:

- FerrovieNord (via Trenord) relies on the ViaggiaTreno API (which is from Trenitalia) and uses their identifiers. However, Trenitalia does not show information on the type of train on ViaggiaTreno; thus, an additional API call to the Trenord website is needed to get the type of train.
- Trentino Trasporti has a bulletin board showing trains moving between stations: [here](http://trainview.algorab.net/). It is not a public API and the data is heavily processed to get something usable.
- Ferrovie Emilia Romagna and Ente Autonomo Volturno have their web departure boards similar to RFI. They are fetched in a similar fashion.

## Netherlands

Just like Sweden, the Netherlands has tremendous support for open data. The data was downloaded from the Rijden de Treinen website: [Rijden de Treinen](https://www.rijdendetreinen.nl/en/open-data). Their API is also used to get the real-time departures.

### Sweden

Sweden has a great, all-encompassing API service for its stations and departures called Trafiklab. The API provides access to real-time data and is user-friendly, making it easy to integrate into applications.

It requires a valid API key, which can be obtained by signing up on the Trafiklab website: [Trafiklab](https://www.trafiklab.se/).

We downloaded the GTFS 2 dataset to get the stations, and then use those IDs using the ResRobot API. Some stations had to be removed, in particular, those situated outside of Sweden.

### Switzerland

Switzerland has a very good API for its stations. The data is available in JSON format and can be obtained from the SBB Open Data website: [SBB API](https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson)

Once the IDs are gathered, they can be used into the Transport API, which relies on the same IDs: [Transport CH](https://transport.opendata.ch/).

### United Kingdom

The UK has a million different services exposing train data, which is fortunate since the UK does not have a national rail service; rather, several operators run the trains. Yet, National Rail uses an airport-like system to identify stations, which is very usueful to us and is the one we use.

The list of stations was downloaded from [Railway Codes](http://www.railwaycodes.org.uk/crs/crs0.shtm).

The API endpoint we use to get the real-time departures is Huxley2: [Huxley2](https://huxley2.azurewebsites.net/)

## Planned systems

### Italy

| Rail infrastructure manager           | Railways                                                        |
| ------------------------------------- | --------------------------------------------------------------- |
| Società Subalpina Imprese Ferroviarie | Domodossola-Locarno                                             |
| Agenzia Mobilità e Trasporti          | Principe-Granarolo, Genova-Casella                              |
| Strutture Trasporto Alto Adige        | L'Assunta-Collalbo, Merano-Malles                               |
| Infrastrutture Venete                 | Adria-Mestre                                                    |
| Rete Ferroviaria Toscana              | Arezzo-Stia, Arezzo-Sinalunga                                   |
| ASTRAL                                | Roma-Civita Castellana-Viterbo, Roma Lido                       |
| ATAC                                  | Roma-Giardinetti                                                |
| Ferrovia Adriatico Sangritana         | Ferrovia Sangritana                                             |
| Ferrovie del Gargano                  | San Severo-Peschici, Foggia-Lucera                              |
| Ferrotramviaria                       | Bari-Barletta, Bari-San Paolo                                   |
| Ferrovie del Sud Est                  | tante                                                           |
| Ferrovie Appulo Lucane                | Bari-Matera-Montalbano Jonico, Altamura-Avigliano-Potenza       |
| Ferrovie della Calabria               | tante                                                           |
| ARST                                  | Macomer-Nuoro, Monserrato-Isili, Sassari-Alghero, Sassari-Sorso |
| FCE                                   | Paternò-Riposto (Circumetnea)                                   |

### Other countries

- Before public release
  - Belgium
  - Denmark
- Later
  - Poland
  - Czech Republic

## Renamed stations

| Station                 | New name 1                    | New name 2                    |
| ----------------------- | ----------------------------- | ----------------------------- |
| Derby                   | Derby (La Salle)              | Derby (UK)                    |
| Westendorf              | Westendorf (Austria)          | Westendorf (Germany)          |
| Maria Rain              | Maria Rain (Austria)          | Maria Rain (Germany)          |
| Bazzano                 | Bazzano (Valsamoggia)         | Bazzano (L'Aquila)            |
| Lison                   | Lison (France)                | Lison (Portogruaro)           |
| Magenta                 | Magenta (Paris)               | Magenta (Milano)              |
| Guarda                  | Guarda (Switzerland)          | Guarda (Molinella)            |
| Castellammare di Stabia | Castellammare di Stabia (RFI) | Castellammare di Stabia (EAV) |
| Montesanto              | Montesanto (Voghiera)         | Montesanto (Napoli, EAV)      |
| Casalnuovo              | Casalnuovo (RFI)              | Casalnuovo (EAV)              |
| Nola                    | Nola (RFI)                    | Nola (EAV)                    |
| Torre del Greco         | Torre del Greco (RFI)         | Torre del Greco (EAV)         |
| Scafati                 | Scafati (RFI)                 | Scafati (EAV)                 |
| Sarno                   | Sarno (RFI)                   | Sarno (EAV)                   |
| Haslach                 | Haslach (Austria)             | Haslach (Germany)             |
| Fors                    | Fors (Sweden)                 | Fors (France)                 |
| Dormans                 | Dormans (France)              | Dormans (UK)                  |
| Bellevue                | Bellevue (France)             | Bellevue (Germany)            |
| Speicher                | Speicher (Switzerland)        | Speicher (Germany)            |
| Ramsen                  | Ramsen (Switzerland)          | Ramsen (Germany)              |
| Horn                    | Horn (Switzerland)            | Horn (Austria)                |
| Rietheim                | Rietheim (Switzerland)        | Rietheim (Germany)            |
| Brunnen                 | Brunnen (Switzerland)         | Brunnen (Germany)             |
| Steinen                 | Steinen (Switzerland)         | Steinen (Germany)             |
| Langendorf              | Langendorf (Switzerland)      | Langendorf (Germany)          |
| Stans                   | Stans (Switzerland)           | Stans (Austria)               |
| Baden                   | Baden (Switzerland)           | Baden (Germany)               |
| Feldbach                | Feldbach (Switzerland)        | Feldbach (Austria)            |

## Removed stations

### RFI

Confinanti con la Svizzera:

```json
{"type": "node", "id": 85099, "lat": 45.8497166, "lon": 8.9441291, "tags": {"ele": "344", "name": "Stabio", "operator": "SBB", "public_transport": "station", "railway": "halt", "railway:ref": "STAF", "station": "train", "train": "yes", "uic_name": "Stabio", "uic_ref": "8517519", "wikidata": "Q18420525", "osm_id": 85099}, "category": "italy_rfi"}
{"type": "node", "id": 1087, "lat": 45.8322299, "lon": 9.0314153, "tags": {"name": "Chiasso", "name:azb": "\u06a9\u06cc\u0627\u0633\u0648", "name:lmo": "Ciass", "old_name:de": "Pias", "operator": "SBB", "public_transport": "station", "railway": "station", "railway:ref": "CHI", "train": "yes", "uic_name": "Chiasso", "uic_ref": "8505307", "wheelchair": "yes", "wikidata": "Q683236", "wikipedia": "it:Stazione di Chiasso", "osm_id": 1087}, "category": "italy_rfi"}
```

Confinanti con la Francia - linea Cuneo - Ventimiglia:

```json
{"type": "node", "id": 1339, "lat": 43.9966378, "lon": 7.5516262, "tags": {"SNCF:stop_name": "Fontan-Saorge", "name": "Fontan - Saorge", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "operator": "SNCF", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775685", "wheelchair": "yes", "wikidata": "Q3096450", "wikipedia": "fr:Gare de Fontan - Saorge", "osm_id": 1339}, "category": "italy_rfi"}
{"type": "node", "id": 1511, "lat": 44.0625669, "lon": 7.6056235, "tags": {"name": "La Brigue", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "La Brigue", "operator": "SNCF", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775687", "wikidata": "Q3096761", "osm_id": 1511}, "category": "italy_rfi"}
{"type": "node", "id": 2826, "lat": 44.0900602, "lon": 7.5940687, "tags": {"name": "Tende", "name:it": "Tenda", "network": "TER Provence-Alpes-C\u00f4te d'Azur", "network:wikidata": "Q3512123", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "Tende", "operator": "SNCF", "operator:wikidata": "Q13646", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775688", "wikidata": "Q2637328", "osm_id": 2826}, "category": "italy_rfi"}
{"type": "node", "id": 2780, "lat": 44.0556825, "lon": 7.5835191, "tags": {"name": "Saint-Dalmas-de-Tende", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "St-Dalmas-de-Tende", "operator": "SNCF", "operator:wikidata": "Q13646", "public_transport": "station", "railway": "station", "source": "cadastre-dgi-fr source : Direction G\u00e9n\u00e9rale des Imp\u00f4ts - Cadastre. Mise \u00e0 jour : 2012", "train": "yes", "uic_ref": "8775686", "wikidata": "Q920420", "osm_id": 2780}, "category": "italy_rfi"}
{"type": "node", "id": 730, "lat": 43.944039, "lon": 7.5163276, "tags": {"name": "Breil sur Roya", "network": "TER Provence-Alpes-C\u00f4te d'Azur", "network:wikidata": "Q3512123", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "Breil-sur-Roya", "operator": "SNCF", "operator:wikidata": "Q13646", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775683", "wheelchair": "yes", "wikidata": "Q1922511", "wikipedia": "fr:Gare de Breil-sur-Roya", "osm_id": 730}, "category": "italy_rfi"}
{"type": "node", "id": 3050, "lat": 44.1125559, "lon": 7.5631346, "tags": {"name": "Vievola", "operator": "SNCF", "public_transport": "stop_position", "railway": "stop", "train": "yes", "uic_ref": "8775689", "osm_id": 3050}, "category": "italy_rfi"}
```

Confinanti con la Francia - linea per Lione:

```json
{"type": "node", "id": 1745, "lat": 45.1933301, "lon": 6.6590437, "tags": {"addr:city": "Modane", "addr:housenumber": "7", "addr:postcode": "73500", "addr:street": "Place Sommeiller", "name": "Modane", "opening_hours": "Mo-Fr 05:00-23:30; Sa 05:00-21:30; Su 05:00-23:30", "operator": "SNCF", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8774200", "website": "https://www.garesetconnexions.sncf/fr/gare/fragr/modane", "wheelchair": "yes", "wikidata": "Q2767199", "wikipedia": "fr:Gare de Modane", "osm_id": 1745}, "category": "italy_rfi"}
{"type":"node","id":1746,"lat":45.1903424,"lon":6.6482279,"tags":{"name":"Modane Fourneaux","operator":"SNCF", "osm_id": 10803999255}, "category": "italy_rfi"}
```

## FN

### Gestite da RFI

```json
{"type":"node","id":"S09999","lat":"45.5432105","lon":"10.1906841","tags":{"name":"Brescia","short_name":"","ref":"S09999","operator":"FN","public_transport":"station","railway":"station","osm_id":"312050243"},"category":"italy_fn"}
{"type":"node","id":"S09998","lat":"45.7845585","lon":"9.0794041","tags":{"name":"Como Camerlata","short_name":"","ref":"S09998","operator":"FN","public_transport":"station","railway":"station","osm_id":"3212140241"},"category":"italy_fn"}
{"type": "node","id": "S01318","lat": 45.6460871,"lon": 9.2029631,"tags": {"description": "Area STIBM: Mi6","name": "Seregno","network": "STIBM","network:wikidata": "Q65125405","operator": "RFI","platforms": "6","public_transport": "station","railway": "station","train": "yes","wikidata": "Q3970949","wikipedia": "it:Stazione di Seregno","osm_id": 248861230},"category":"italy_fn"}
{"type":"node","lat":45.5777772,"lon":9.2728213,"tags":{"description":"Area STIBM: Mi4","name":"Monza","network":"STIBM","operator":"RFI;Centostazioni","platforms":"6","public_transport":"station","railway":"station","wheelchair":"yes","wikidata":"Q801199","wikipedia":"it:Stazione di Monza","osm_id":256975055},"category":"italy_fn"}
{"type":"node","id":"S01206","lat":45.8378369,"lon":8.9073973,"tags":{"name":"Cantello-Gaggiolo","railway":"halt","osm_id":1543102156},"category":"italy_fn"}
{"type":"node","id":"S01030","lat":45.6598865,"lon":8.7984831,"tags":{"internet_access":"no","name":"Gallarate","network":"RFI","network:wikidata":"Q1060049","operator":"RFI","platforms":"5","public_transport":"station","railway":"station","train":"yes","wheelchair":"yes","wheelchair:description":"-ascensori con diversi orari -bagni a pagamento","osm_id":251033595},"category":"italy_fn"}
```

Duplicate senza ID:

* Sesto San Giovanni
* Monza

## Dismesse

```json
{"type":"node","lat":45.8587444,"lon":10.158937,"tags":{"disused":"yes","name":"Artogne - Gianico","operator":"FNM","public_transport":"stop_position","railway":"stop","train":"yes","wikidata":"Q34701063","osm_id":7772999053},"category":"italy_fn"}
{"type":"node","id":"","lat":46.0901543,"lon":10.3149439,"tags":{"name":"Forno d'Allione","operator":"FNM","public_transport":"stop_position","railway":"halt","train":"yes","wikidata":"Q21615984","wikipedia":"it:Stazione di Forno d'Allione","osm_id":312271164},"category":"italy_fn"}
{"type":"node","id":"","lat":45.5471337,"lon":10.1530124,"tags":{"disused:railway":"halt","name":"Mandolossa","operator":"Trenord","public_transport":"stop_position","railway":"stop","train":"yes","wikidata":"Q3970029","wikipedia":"it:Stazione di Mandolossa","osm_id":665529059},"category":"italy_fn"}
{"type":"node","id":"","lat":45.981461,"lon":10.3258378,"tags":{"name":"Niardo","public_transport":"stop_position","railway":"halt","train":"yes","osm_id":1976777276},"category":"italy_fn"}
{"type":"node","id":"","lat":46.0535009,"lon":10.3489097,"tags":{"name":"Sellero","operator":"Ferrovienord","public_transport":"stop_position","railway":"stop","train":"yes","osm_id":9105549613},"category":"italy_fn"}
{"type":"node","id":"","lat":45.8198645,"lon":8.9242211,"tags":{"abandoned:railway":"station","internet_access":"no","name":"Rodero-Valmorea","network":"FerrovieNord","public_transport":"station","railway":"station","start_date":"1915-12-31","train":"yes","wikidata":"Q18289249","wikimedia_commons":"Category:Valmorea_train_station","wikipedia":"it:Stazione di Valmorea","osm_id":11116194967},"category":"italy_fn"}
```

Dismesse senza ID:

* Erbanno
* Lezza-Carpesino
* Lido di Turbigo
* Sacconago

## Sweden

```json
{"type": "node", "id": 740076297, "lat": 62.268399, "lon": 17.37687, "tags": {"name": "Njurunda Resec", "private_code": "66663", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "22", "sellable": "true"}, "category": "sweden_trafikverket"}
```

```json
{"type": "node", "id": 800001301, "lat": 51.0658, "lon": 13.7408, "tags": {"name": "Dresden-Neustadt", "short_name": "Dresden-Neustdt", "private_code": "72891", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 800009333, "lat": 50.8397, "lon": 12.9308, "tags": {"name": "Chemnitz Hbf", "short_name": "Chemnitz Hbf", "private_code": "73177", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "false"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 800010100, "lat": 52.5256, "lon": 13.3694, "tags": {"name": "Berlin Hbf (Tief)", "short_name": "Berlin Hbf", "private_code": "72893", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true", "abbreviation": "ZBLN"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 800020400, "lat": 53.5528, "lon": 10.0069, "tags": {"name": "Hamburg Hbf", "short_name": "Hamburg Hbf", "private_code": "72895", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true", "abbreviation": "ZAH"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 800024643, "lat": 54.076376, "lon": 9.979938, "tags": {"name": "Neumuenster", "private_code": "71568", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 800080603, "lat": 48.1275, "lon": 11.605, "tags": {"name": "Muenchen Ost", "short_name": "Muenchen Ost", "private_code": "72896", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000308, "lat": 47.4178, "lon": 13.22, "tags": {"name": "Bischofshofen", "short_name": "Bischofshofen", "private_code": "72898", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000310, "lat": 47.3483, "lon": 13.195, "tags": {"name": "St Johann im Pongau", "short_name": "S Johann Pongau", "private_code": "72899", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000320, "lat": 47.3206, "lon": 12.7967, "tags": {"name": "Zell am See", "short_name": "Zell am See", "private_code": "72900", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000329, "lat": 47.4542, "lon": 12.3911, "tags": {"name": "Kitzbuehel", "short_name": "Kitzbuehel", "private_code": "72901", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000334, "lat": 47.4489, "lon": 12.3092, "tags": {"name": "Kirchberg in Tirol", "short_name": "Kirchberg Tirol", "private_code": "72902", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000378, "lat": 47.1275, "lon": 10.2669, "tags": {"name": "St Anton am Arlberg", "short_name": "S Anton Arlberg", "private_code": "72903", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000462, "lat": 47.8131, "lon": 13.0458, "tags": {"name": "Salzburg Hbf", "short_name": "Salzburg Hbf", "private_code": "72904", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000482, "lat": 47.1117, "lon": 13.1325, "tags": {"name": "Bad Gastein", "short_name": "Bad Gastein", "private_code": "72905", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000509, "lat": 47.3883, "lon": 11.7783, "tags": {"name": "Jenbach", "short_name": "Jenbach", "private_code": "72906", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000522, "lat": 47.2633, "lon": 11.4006, "tags": {"name": "Innsbruck Hbf", "short_name": "Innsbruck Hbf", "private_code": "72907", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810000626, "lat": 47.3939, "lon": 13.6781, "tags": {"name": "Schladming", "short_name": "Schladming", "private_code": "72908", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 810099994, "lat": 48.2347, "lon": 16.5044, "tags": {"name": "Wien Aspern Nord", "short_name": "Wien Aspern Nor", "private_code": "72915", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "false"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000083, "lat": 55.4906, "lon": 9.4808, "tags": {"name": "Kolding", "short_name": "Kolding", "private_code": "72885", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000512, "lat": 55.4017, "lon": 10.3867, "tags": {"name": "Odense", "short_name": "Odense", "private_code": "72886", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true", "abbreviation": "ZOD"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000626, "lat": 55.672692, "lon": 12.564631, "tags": {"name": "K\u00f8benhavn H", "short_name": "K\u00f8benhavn H", "private_code": "25315", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "preferredInterchange", "alt_name": "K\u00f8benhavn H", "abbreviation": "ZKH", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000646, "lat": 55.684016, "lon": 12.572808, "tags": {"name": "K\u00f8benhavn N\u00f8rreport", "short_name": "K\u00f8benhavn N", "private_code": "25318", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "preferredInterchange", "alt_name": "K\u00f8benhavn N\u00f8rreport", "abbreviation": "ZKN", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000650, "lat": 55.692882, "lon": 12.588034, "tags": {"name": "K\u00f8benhavn \u00d8sterport", "short_name": "K\u00f8benhavn \u00d8", "private_code": "25317", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "preferredInterchange", "alt_name": "K\u00f8benhavn \u00d8sterport", "abbreviation": "ZKK", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000667, "lat": 55.996331, "lon": 12.550814, "tags": {"name": "Esperg\u00e6rde", "short_name": "Esperg\u00e6rde", "private_code": "25320", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "alt_name": "Esperg\u00e6rde", "abbreviation": "ZGAE", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000783, "lat": 55.6525, "lon": 12.5167, "tags": {"name": "K\u00f6benhavn Syd", "short_name": "K\u00f6benhavn Syd", "private_code": "72887", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000798, "lat": 55.6486, "lon": 12.2694, "tags": {"name": "H\u00f6je Taastrup", "short_name": "H\u00f6je Taastrup", "private_code": "72888", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "owner": "50", "sellable": "true", "abbreviation": "ZHT\u00c5"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000856, "lat": 55.628681, "lon": 12.579547, "tags": {"name": "\u00d8restad", "short_name": "\u00d8restad", "private_code": "25313", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "interchangeAllowed", "alt_name": "\u00d8restad", "abbreviation": "Z\u00d6RE", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000857, "lat": 55.629746, "lon": 12.601651, "tags": {"name": "T\u00e5rnby", "short_name": "T\u00e5rnby", "private_code": "23657", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "recommendedInterchange", "owner": "50", "sellable": "true", "abbreviation": "ZT\u00c5T"}, "category": "sweden_trafikverket"}
{"type": "node", "id": 860000858, "lat": 55.629429, "lon": 12.649696, "tags": {"name": "CPH Airport", "short_name": "CPH Airport", "private_code": "25314", "transport_mode": "rail", "stop_place_type": "railStation", "weighting": "preferredInterchange", "alt_name": "CPH Airport", "abbreviation": "ZCPH", "owner": "50", "sellable": "true"}, "category": "sweden_trafikverket"}
```

## Belgium

These stations lie outside of Belgium but are included in the NMBS/SNCB network. They are used for international connections, especially to France.

```json
{"type": "node", "id": "BE.NMBS.008778127", "lat": 43.317498, "lon": 3.4658, "tags": {"name": "Agde"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008774164", "lat": 45.673624, "lon": 6.383617, "tags": {"name": "Albertville"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008775767", "lat": 43.586618, "lon": 7.1201361, "tags": {"name": "Antibes"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008734201", "lat": 50.28683, "lon": 2.78169, "tags": {"name": "Arras"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008729560", "lat": 50.19744, "lon": 3.843413, "tags": {"name": "Aulnoye-Aymeries"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008778100", "lat": 43.336177, "lon": 3.218794, "tags": {"name": "B\u00e9ziers"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008774179", "lat": 45.618826, "lon": 6.771664, "tags": {"name": "Bourg-Saint-Maurice"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008775762", "lat": 43.553742, "lon": 7.019895, "tags": {"name": "Cannes"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008701687", "lat": 49.263889, "lon": 2.469167, "tags": {"name": "Creil"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008774177", "lat": 45.574194, "lon": 6.733522, "tags": {"name": "Landry"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008775544", "lat": 43.4555673, "lon": 6.4826446, "tags": {"name": "Les Arcs - Draguignan"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008722326", "lat": 50.6391167, "lon": 3.0756612, "tags": {"name": "Lille Europe"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008714210", "lat": 48.9475, "lon": 6.169722, "tags": {"name": "Lorraine TGV"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008739370", "lat": 48.725758, "lon": 2.261254, "tags": {"name": "Massy TGV"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008729500", "lat": 50.27289, "lon": 3.966566, "tags": {"name": "Maubeuge"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008748100", "lat": 47.216148, "lon": -1.542356, "tags": {"name": "Nantes"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008778110", "lat": 43.190399, "lon": 3.00601, "tags": {"name": "Narbonne"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008777500", "lat": 43.832602, "lon": 4.365997, "tags": {"name": "N\u00eemes"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008778400", "lat": 42.695938, "lon": 2.879397, "tags": {"name": "Perpignan"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008728683", "lat": 50.624164, "lon": 3.1275, "tags": {"name": "Pont de Bois"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008747100", "lat": 48.103517, "lon": -1.672744, "tags": {"name": "Rennes"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008721222", "lat": 48.744798, "lon": 7.362255, "tags": {"name": "Saverne"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008777320", "lat": 43.41281, "lon": 3.696535, "tags": {"name": "S\u00e8te"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008721202", "lat": 48.585437, "lon": 7.733905, "tags": {"name": "Strasbourg"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008775500", "lat": 43.1274781, "lon": 5.9326648, "tags": {"name": "Toulon"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008015199", "lat": 50.78078, "lon": 6.07055, "tags": {"name": "Aachen West"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008010053", "lat": 51.517898, "lon": 7.459293, "tags": {"name": "Dortmund Hbf"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008010316", "lat": 51.42978, "lon": 6.7759037, "tags": {"name": "Duisburg Hbf"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008015190", "lat": 50.8709, "lon": 6.0944, "tags": {"name": "Herzogenrath"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008003040", "lat": 49.699371, "lon": 7.321228, "tags": {"name": "Idar-Oberstein"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008015458", "lat": 50.942721, "lon": 6.958823, "tags": {"name": "K\u00f6ln Hbf"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008014008", "lat": 49.479722, "lon": 8.469722, "tags": {"name": "Mannheim Hbf"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008302593", "lat": 45.440975, "lon": 12.321039, "tags": {"name": "Venezia Santa Lucia"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400081", "lat": 52.394175, "lon": 5.277962, "tags": {"name": "Almere Buiten"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400080", "lat": 52.375, "lon": 5.217778, "tags": {"name": "Almere Centrum"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400061", "lat": 52.338865, "lon": 4.871946, "tags": {"name": "Amsterdam Zuid"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400131", "lat": 51.594459, "lon": 4.7764, "tags": {"name": "Breda"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400219", "lat": 50.772135, "lon": 5.709786, "tags": {"name": "Eijsden"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400307", "lat": 50.89095, "lon": 5.974577, "tags": {"name": "Heerlen"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400548", "lat": 50.89651, "lon": 6.019776, "tags": {"name": "Landgraaf"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400424", "lat": 50.85, "lon": 5.705392, "tags": {"name": "Maastricht"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400426", "lat": 50.838502, "lon": 5.716707, "tags": {"name": "Maastricht Randwyck"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400434", "lat": 50.8826, "lon": 5.750631, "tags": {"name": "Meerssen"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400526", "lat": 51.540834, "lon": 4.458692, "tags": {"name": "Roosendaal"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400621", "lat": 52.089167, "lon": 5.109722, "tags": {"name": "Utrecht Centraal"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.008400632", "lat": 50.86928, "lon": 5.832888, "tags": {"name": "Valkenburg"}, "category": "belgium_all"}
{"type": "node", "id": "BE.NMBS.007054650", "lat": 51.5031, "lon": -0.1132, "tags": {"name": "London Waterloo"}, "category": "belgium_all"}
```