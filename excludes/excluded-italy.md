# Removed Italy stations

## RFI

The following RFI stations were removed since they lie outside of Italy.

On the border with Switzerland:

```json
{"type": "node", "id": 85099, "lat": 45.8497166, "lon": 8.9441291, "tags": {"ele": "344", "name": "Stabio", "operator": "SBB", "public_transport": "station", "railway": "halt", "railway:ref": "STAF", "station": "train", "train": "yes", "uic_name": "Stabio", "uic_ref": "8517519", "wikidata": "Q18420525", "osm_id": 85099}, "category": "italy_rfi"}
{"type": "node", "id": 1087, "lat": 45.8322299, "lon": 9.0314153, "tags": {"name": "Chiasso", "name:azb": "\u06a9\u06cc\u0627\u0633\u0648", "name:lmo": "Ciass", "old_name:de": "Pias", "operator": "SBB", "public_transport": "station", "railway": "station", "railway:ref": "CHI", "train": "yes", "uic_name": "Chiasso", "uic_ref": "8505307", "wheelchair": "yes", "wikidata": "Q683236", "wikipedia": "it:Stazione di Chiasso", "osm_id": 1087}, "category": "italy_rfi"}
```

On the border with France (Cuneo - Ventimiglia line):

```json
{"type": "node", "id": 1339, "lat": 43.9966378, "lon": 7.5516262, "tags": {"SNCF:stop_name": "Fontan-Saorge", "name": "Fontan - Saorge", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "operator": "SNCF", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775685", "wheelchair": "yes", "wikidata": "Q3096450", "wikipedia": "fr:Gare de Fontan - Saorge", "osm_id": 1339}, "category": "italy_rfi"}
{"type": "node", "id": 1511, "lat": 44.0625669, "lon": 7.6056235, "tags": {"name": "La Brigue", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "La Brigue", "operator": "SNCF", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775687", "wikidata": "Q3096761", "osm_id": 1511}, "category": "italy_rfi"}
{"type": "node", "id": 2826, "lat": 44.0900602, "lon": 7.5940687, "tags": {"name": "Tende", "name:it": "Tenda", "network": "TER Provence-Alpes-C\u00f4te d'Azur", "network:wikidata": "Q3512123", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "Tende", "operator": "SNCF", "operator:wikidata": "Q13646", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775688", "wikidata": "Q2637328", "osm_id": 2826}, "category": "italy_rfi"}
{"type": "node", "id": 2780, "lat": 44.0556825, "lon": 7.5835191, "tags": {"name": "Saint-Dalmas-de-Tende", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "St-Dalmas-de-Tende", "operator": "SNCF", "operator:wikidata": "Q13646", "public_transport": "station", "railway": "station", "source": "cadastre-dgi-fr source : Direction G\u00e9n\u00e9rale des Imp\u00f4ts - Cadastre. Mise \u00e0 jour : 2012", "train": "yes", "uic_ref": "8775686", "wikidata": "Q920420", "osm_id": 2780}, "category": "italy_rfi"}
{"type": "node", "id": 730, "lat": 43.944039, "lon": 7.5163276, "tags": {"name": "Breil sur Roya", "network": "TER Provence-Alpes-C\u00f4te d'Azur", "network:wikidata": "Q3512123", "note:railway": "Un seul tag railway=station par gare. A mettre sur un node au milieu des voies", "official_name": "Breil-sur-Roya", "operator": "SNCF", "operator:wikidata": "Q13646", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8775683", "wheelchair": "yes", "wikidata": "Q1922511", "wikipedia": "fr:Gare de Breil-sur-Roya", "osm_id": 730}, "category": "italy_rfi"}
{"type": "node", "id": 3050, "lat": 44.1125559, "lon": 7.5631346, "tags": {"name": "Vievola", "operator": "SNCF", "public_transport": "stop_position", "railway": "stop", "train": "yes", "uic_ref": "8775689", "osm_id": 3050}, "category": "italy_rfi"}
```

On the border with France (Turin - Modane line):

```json
{"type": "node", "id": 1745, "lat": 45.1933301, "lon": 6.6590437, "tags": {"addr:city": "Modane", "addr:housenumber": "7", "addr:postcode": "73500", "addr:street": "Place Sommeiller", "name": "Modane", "opening_hours": "Mo-Fr 05:00-23:30; Sa 05:00-21:30; Su 05:00-23:30", "operator": "SNCF", "public_transport": "station", "railway": "station", "train": "yes", "uic_ref": "8774200", "website": "https://www.garesetconnexions.sncf/fr/gare/fragr/modane", "wheelchair": "yes", "wikidata": "Q2767199", "wikipedia": "fr:Gare de Modane", "osm_id": 1745}, "category": "italy_rfi"}
{"type":"node","id":1746,"lat":45.1903424,"lon":6.6482279,"tags":{"name":"Modane Fourneaux","operator":"SNCF", "osm_id": 10803999255}, "category": "italy_rfi"}
```

## FN

### RFI stations

These RFI stations appear also in the FN network and thus were removed to avoid duplicates.

```json
{"type":"node","id":"S09999","lat":"45.5432105","lon":"10.1906841","tags":{"name":"Brescia","short_name":"","ref":"S09999","operator":"FN","public_transport":"station","railway":"station","osm_id":"312050243"},"category":"italy_fn"}
{"type":"node","id":"S09998","lat":"45.7845585","lon":"9.0794041","tags":{"name":"Como Camerlata","short_name":"","ref":"S09998","operator":"FN","public_transport":"station","railway":"station","osm_id":"3212140241"},"category":"italy_fn"}
{"type": "node","id": "S01318","lat": 45.6460871,"lon": 9.2029631,"tags": {"description": "Area STIBM: Mi6","name": "Seregno","network": "STIBM","network:wikidata": "Q65125405","operator": "RFI","platforms": "6","public_transport": "station","railway": "station","train": "yes","wikidata": "Q3970949","wikipedia": "it:Stazione di Seregno","osm_id": 248861230},"category":"italy_fn"}
{"type":"node","lat":45.5777772,"lon":9.2728213,"tags":{"description":"Area STIBM: Mi4","name":"Monza","network":"STIBM","operator":"RFI;Centostazioni","platforms":"6","public_transport":"station","railway":"station","wheelchair":"yes","wikidata":"Q801199","wikipedia":"it:Stazione di Monza","osm_id":256975055},"category":"italy_fn"}
{"type":"node","id":"S01206","lat":45.8378369,"lon":8.9073973,"tags":{"name":"Cantello-Gaggiolo","railway":"halt","osm_id":1543102156},"category":"italy_fn"}
{"type":"node","id":"S01030","lat":45.6598865,"lon":8.7984831,"tags":{"internet_access":"no","name":"Gallarate","network":"RFI","network:wikidata":"Q1060049","operator":"RFI","platforms":"5","public_transport":"station","railway":"station","train":"yes","wheelchair":"yes","wheelchair:description":"-ascensori con diversi orari -bagni a pagamento","osm_id":251033595},"category":"italy_fn"}
```

The following RFI stations were removed manually since they are part of the FN network but were not matched automatically:

* Sesto San Giovanni
* Monza

## Disused stations

The following FN stations were removed since they have seen no traffic for a long time or have been officially closed, yet they are still present in the FN dataset.

```json
{"type":"node","lat":45.8587444,"lon":10.158937,"tags":{"disused":"yes","name":"Artogne - Gianico","operator":"FNM","public_transport":"stop_position","railway":"stop","train":"yes","wikidata":"Q34701063","osm_id":7772999053},"category":"italy_fn"}
{"type":"node","id":"","lat":46.0901543,"lon":10.3149439,"tags":{"name":"Forno d'Allione","operator":"FNM","public_transport":"stop_position","railway":"halt","train":"yes","wikidata":"Q21615984","wikipedia":"it:Stazione di Forno d'Allione","osm_id":312271164},"category":"italy_fn"}
{"type":"node","id":"","lat":45.5471337,"lon":10.1530124,"tags":{"disused:railway":"halt","name":"Mandolossa","operator":"Trenord","public_transport":"stop_position","railway":"stop","train":"yes","wikidata":"Q3970029","wikipedia":"it:Stazione di Mandolossa","osm_id":665529059},"category":"italy_fn"}
{"type":"node","id":"","lat":45.981461,"lon":10.3258378,"tags":{"name":"Niardo","public_transport":"stop_position","railway":"halt","train":"yes","osm_id":1976777276},"category":"italy_fn"}
{"type":"node","id":"","lat":46.0535009,"lon":10.3489097,"tags":{"name":"Sellero","operator":"Ferrovienord","public_transport":"stop_position","railway":"stop","train":"yes","osm_id":9105549613},"category":"italy_fn"}
{"type":"node","id":"","lat":45.8198645,"lon":8.9242211,"tags":{"abandoned:railway":"station","internet_access":"no","name":"Rodero-Valmorea","network":"FerrovieNord","public_transport":"station","railway":"station","start_date":"1915-12-31","train":"yes","wikidata":"Q18289249","wikimedia_commons":"Category:Valmorea_train_station","wikipedia":"it:Stazione di Valmorea","osm_id":11116194967},"category":"italy_fn"}
```

The following disused FN stations were removed manually since they were not matched automatically:

* Erbanno
* Lezza-Carpesino
* Lido di Turbigo
* Sacconago
