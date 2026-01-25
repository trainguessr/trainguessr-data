# Trainguessr railway stations dataset

This repository contains a dataset of geolocated railway stations across various European countries, along with scripts to generate and update the data.

This README provides information about the data sources used for each country, instructions on how to generate the datasets, and notes on any removed or renamed stations.

## Data sources

### Austria

Austria has good open data, but a somewhat janky API for real time departures. The API ([here](https://fahrplan.oebb.at/bin/stboard.exe/dn)) returns JavaScript objects, which are then parsed and converted to JSON. The API is not documented, but it works well enough.

The list of stations was obtained from the ÖBB open data website: [ÖBB](https://data.oebb.at/de/datensaetze~geo-netz~).

To get started, cd into `gen/` and run `python3 austria.py`.

Given the size of the dataset, the script will cache the stations data locally in the `cache/` folder.

### Belgium

Infrabel exports its stations as open data in a JSON file [here](https://opendata.infrabel.be/explore/dataset/operationele-punten-van-het-netwerk/export/?sort=ptcarid).

Trainguessr uses the iRail API ([here](https://docs.irail.be/#)) as it makes things way easier. Stations and live departures are obtained from the iRail API, which is a public API that does not require an API key.

To get started, cd into `gen/` and run `python3 belgium.py`.

### France

SCNF export its stations as open data in a JSON file [here](https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe%2FBerlin).

These station IDs are then used in the SNCF API, which requires an API key. The API key is obtained by creating a free account on the SNCF Numerique website: [SNCF Numerique](https://numerique.sncf.com/).

To get started, cd into `gen/` and run `python3 france.py`. THe API key is not needed to get the stations, only for the real-time departures.


### Germany

The German railway system is a bit of a mess. The Deutsche Bahn API is not public, but it is possible to get the real time departures from the DB website: [DB](https://www.bahnhof.de/api/boards). The list of stations is obtained from the DB open data website: [DB Open Data](https://data.deutschebahn.com/). It thankfully uses UIC codes.

To get started, we rely on the `db-stations` Node.js package to get the list of stations. Thus, first run the `gen/germany.sh` script to download the package and extract the data. It will be stored in the `cache/germany/full.json` and `cache/germany/data.json` files. To use the script, make sure you have Docker installed.

Then, cd into `gen/` and run `python3 germany.py`.

### Italy

#### RFI

Italy has a fragmented railway system with many different operators. The main rail infrastructure manager is RFI (Rete Ferroviaria Italiana), which manages most of the national railway network.

Italy's RFI is notorious for its lack of public APIs. This website, written in pure HTML, allows someone to query data about train schedules and routes: [RFI](https://www.rfi.it/it/stazioni/pagine-stazioni/servizi-di-qualita/informazioni-al-pubblico/monitor-arrivi-partenze-live.html).

This dataset was compiled by _manually_ matching each RFI station to its geolocation data from OpenStreetMap. As a result, updating the dataset requires manual intervention to ensure accuracy.

#### Other operators

All non-RFI stations (at the time of writing: Ferrovie Nord, Trentino Trasporti, Ferrovie Emilia Romagna, Ente Autonomo Volturno) each have their own API and data sources:

- FerrovieNord (Trenord) relies on the ViaggiaTreno API (which is from Trenitalia) and uses their identifiers. The list of stations was scraped from ViaggiaTreno and manually matched to geolocation data.
- Trentino Trasporti has a bulletin board showing trains moving between stations: [here](http://trainview.algorab.net/). It is not a documented API and the data was scraped and heavily processed to get something usable. Again, the stations were manually matched to geolocation data.
- Ferrovie Emilia Romagna and Ente Autonomo Volturno have their web departure boards similar to RFI. They are fetched in a similar fashion.

All these non-RFI stations were matched to their geolocation data manually and thus require manual updates.

### Netherlands

Just like Sweden, the Netherlands has tremendous support for open data. The data was downloaded from the Rijden de Treinen website: [Rijden de Treinen](https://www.rijdendetreinen.nl/en/open-data). Their API is also used to get the real-time departures.

To get started, cd into `gen/` and run `python3 netherlands.py`.

### Switzerland

Switzerland has a very good API for its stations. The data is available in JSON format and can be obtained from the SBB Open Data website: [SBB API](https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson)

Once the IDs are gathered, they can be used into the Transport API, which relies on the same IDs: [Transport CH](https://transport.opendata.ch/).

To get started, cd into `gen/` and run `python3 switzerland.py`.

### Sweden

Sweden has a great, all-encompassing API service for its stations and departures called Trafiklab. The API provides access to real-time data and is user-friendly, making it easy to integrate into applications.

It requires a valid API key, which can be obtained by signing up on the Trafiklab website: [Trafiklab](https://www.trafiklab.se/). Add your API key to the `.env-secret` file: `export TRAFIKLAB_API_KEY_STOPS=...`. Remember to use the correct "Stops data" API key since Trafiklab provides different keys for different datasets.

We downloaded the Stops dataset to get the stations. Some stations had to be removed, in particular, those situated outside of Sweden.

Once you have your API key, cd into `gen/` and run `python3 sweden.py`.

Given the low rate of requests allowed by the Trafiklab API, the script will cache the GTFS dataset locally in the `cache/` folder. If you want to refresh the cache, just delete the `cache/sweden.zip` file.

Currently, there are some stations that are actually in Norway but have not been removed yet.

### United Kingdom

The UK has a million different services exposing train data, which is fortunate since the UK does not have a national rail service; rather, several operators run the trains. Yet, National Rail uses an airport-like system to identify stations, which is very usueful to us and is the one we use.

The lists of stations are roughly public and can be downloaded from several sources, like from [Railway Codes](http://www.railwaycodes.org.uk/crs/crs0.shtm). Ours comes from this repository: [UK Railway Stations](https://github.com/davwheat/uk-railway-stations).

The API endpoint we use to get the real-time departures is Huxley2: [Huxley2](https://huxley2.azurewebsites.net/).

To get started, cd into `gen/` and run `python3 uk.py`.

## Removed stations

### Belgium

The `changes/excluded-belgium.json` file contains a list of stations that were removed. These stations lie outside of Belgium but are included in the NMBS/SNCB network. They are used for international connections, especially to France.

The script that generates the Belgium stations (`gen/belgium.py`) automatically removes these stations.

### Italy

Since a lot of manual work was done to match the RFI stations to their geolocation data, no automatic removal of stations is implemented.

Nevertheless, the `changes/excluded-italy.md` file contains a list of stations that were removed along with a small explanation for each of the removal(s).

### Sweden

The `changes/excluded-sweden.json` file contains a list of stations that were removed. These stations lie outside of Sweden but are included in the Trafikverket network. They are used for international connections, especially to Denmark and Germany.

The script that generates the Sweden stations (`gen/sweden.py`) automatically removes these stations.

As mentioned above, some stations in Norway are still present in the dataset.

### Switzerland

The Switzerland dataset only contains stations within Switzerland, so no removal was necessary.

## Renamed stations

In the `changes/` folder, there are files that contain a list of renamed stations for each country (and operator). These stations were renamed to avoid confusion with other stations with the same name in different countries or different operators within the same country.

## Missing stations

### Italy

Several rail infrastructure managers exist in Italy apart from RFI. These smaller companies manage regional railways and often have their own APIs or data sources. However, gathering data from all these different sources is challenging to say the least.

| Rail infrastructure manager           | Railways                                                        |
| ------------------------------------- | --------------------------------------------------------------- |
| Società Subalpina Imprese Ferroviarie | Domodossola-Locarno (from Ribellasca to Domodossola)            |
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

The Domodossola-Locarno line is managed by Società Subalpina Imprese Ferroviarie (SSIF) and connects Italy to Switzerland. SSIF links with the Swiss Federal Railways (SBB) in Switzerland territory and those stations are already included in the Switzerland dataset; however, the Italian stations are missing (from Ribellasca to Domodossola).

## Contributing

Contributions to this dataset are welcome! If you find any errors, missing stations, or have suggestions for improvements, please open an issue or submit a pull request.

When submitting changes, please ensure that you provide clear explanations and references for any modifications made to the dataset. This will help maintain the accuracy and reliability of the data for all users.

## License

A vast majority of the data sources used in this dataset are open data or publicly accessible APIs. The overall dataset is licensed under the [Open Database License (ODbL)]([https://opendatacommons.org/licenses/odbl/1.0/) and has been compiled with data from OpenStreetMap and other open data sources. Please refer to the individual data sources for their specific licensing terms.

The data that was scraped from websites without public APIs is intended for personal and non-commercial use only. Please respect the terms of service of the original data providers when using this dataset.
