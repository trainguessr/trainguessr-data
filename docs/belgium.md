# Belgium

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Belgium | `belgium_all` | iRail/NMBS-SNCB | `gen/belgium.py`; Infrabel cross-check | 603 nodes; no confirmed mainstream iRail omission. Twenty heritage stations require five named operator-specific providers; urban metro/tram is separate. |

## Generation and source notes

Infrabel exports its stations as open data in a JSON file [here](https://opendata.infrabel.be/explore/dataset/operationele-punten-van-het-netwerk/export/?sort=ptcarid).

TrainGuessr uses the public [iRail API](https://docs.irail.be/) for station and
live-departure data. It does not require an API key.

Run `python3 gen/belgium.py` from the repository root.


## Detailed review notes

## Provider and infrastructure sources

- iRail station namespace: <https://api.irail.be/v1/stations?format=json&lang=en>
- iRail liveboard verification: <https://api.irail.be/v1/liveboard/>
- Infrabel operational points: <https://opendata.infrabel.be/api/explore/v2.1/catalog/datasets/operationele-punten-van-het-netwerk/records>
- OSM discovery via Overpass: <https://overpass-api.de/api/interpreter>

TrainGuessr uses iRail/NMBS-SNCB IDs for `belgium_all`. OSM and Infrabel are
used to verify physical railway locations, not as runtime provider namespaces.

## Reviewed iRail records

The live iRail station response contains 714 `BE.NMBS.*` records. The following
14 records are confirmed Belgian passenger-station locations through the
OSM/Infrabel crosswalk and are accepted by the iRail liveboard endpoint. Empty
boards are included when the physical station exists and the provider accepts
the ID.

| iRail ID | Name |
| --- | --- |
| `BE.NMBS.008811155` | Haren |
| `BE.NMBS.008814472` | Arcaden/Arcades |
| `BE.NMBS.008821147` | Mortsel |
| `BE.NMBS.008821337` | Hove |
| `BE.NMBS.008822459` | Hever |
| `BE.NMBS.008844644` | Hergenrath |
| `BE.NMBS.008863115` | Jambes |
| `BE.NMBS.008866258` | Neufchâteau |
| `BE.NMBS.008881190` | Lens |
| `BE.NMBS.008882339` | Leval |
| `BE.NMBS.008893039` | Melle |
| `BE.NMBS.008894821` | Zwijndrecht |
| `BE.NMBS.008895646` | Herne |
| `BE.NMBS.008896412` | Comines |

`BE.NMBS.008869047` (`Athus-Frontiere`) is excluded: the audit did not
find an exact Belgian passenger-station match for this border-point record.
Nearby or related station records are separate where the provider lists
separate IDs.

The 14 records above are playable, and 111 records are explicitly excluded.
The exclusions include foreign
international records; 29 excluded records still have Belgian-area
coordinates and require separate evidence rather than automatic inclusion.

## Crosswalk findings

The Infrabel API returned 1,359 operational points. Of these, 425 were
classified as `Station` and 325 as `Stop in open track`; the dataset also
contains freight, junction, and other operational locations, so those classes
were not promoted wholesale into the passenger catalogue. The 750
station/stop records include 111 points more than 1 km from the nearest iRail
station because Infrabel coordinates many operational points within a station
area separately.

The Belgian Overpass query for `railway=station|halt` returned 720 elements,
716 with names. The nearest iRail station was within 500 m for 585 elements,
within 1,000 m for 632, and over 1,000 m for 84. The 84 long-distance
candidates divide into 62 urban STIB/TEC/De Lijn records, the already
represented Dolhain-Gileppe record, the restored Hergenrath record, and the
following 20 extant tourist-rail stations. The 20 have no iRail/NMBS identity;
they are named provider gaps rather than guessed `belgium_all` nodes.

| Heritage system | Extant station or halt | Coordinates |
| --- | --- | --- |
| Stoomtrein Dendermonde-Puurs (SDP) | Baasrode-Noord | 51.028921, 4.178808 |
| SDP | Buggenhout a/d Schelde | 51.033646, 4.193460 |
| SDP | Sint-Amands | 51.051527, 4.206700 |
| SDP | Oppuurs | 51.070282, 4.245181 |
| SDP | Sint-Pietersburcht | 51.075023, 4.263494 |
| CFV3V | Nismes | 50.084580, 4.557623 |
| CFV3V | Olloy-sur-Viroin | 50.073133, 4.602714 |
| CFV3V | Vierves | 50.078035, 4.634980 |
| CFV3V | Treignes | 50.090535, 4.682520 |
| PFT/TSP | Braibant | 50.316938, 5.067629 |
| PFT/TSP | Dorinne-Durnal | 50.326162, 4.977897 |
| PFT/TSP | Évrehailles | 50.333978, 4.930884 |
| PFT/TSP | Purnode | 50.323408, 4.941530 |
| PFT/TSP | Senenne | 50.316782, 5.024651 |
| PFT/TSP | Spontin | 50.322966, 5.009944 |
| Stoomtrein Maldegem-Eeklo | Balgerhoeke | 51.203902, 3.517543 |
| Stoomcentrum Maldegem | Maldegem | 51.204838, 3.446535 |
| Rail Rebecq Rognon | Bloc U | 50.658168, 4.101849 |
| Rail Rebecq Rognon | Rebecq | 50.660734, 4.133375 |
| Rail Rebecq Rognon | Rognon | 50.651986, 4.106677 |

Baasrode-Noord has an OSM `abandoned:railway=station` tag, but the
Dendermonde-Puurs source confirms that the station building, railway, and
tourist passenger route are in use. It is therefore a provider-gap record,
not a dismantled-site exclusion. The Dendermonde-Puurs route and station
history are documented at
<https://nl.wikipedia.org/wiki/Stoomtrein_Dendermonde-Puurs> and
<https://nl.wikipedia.org/wiki/Station_Baasrode-Noord>.

The heritage candidates require separate operator-specific timetable providers
if heritage rail is later enabled. Metro/tram records and operational-only
points are out of scope for `belgium_all`.

## Attribution and provider constraints

- Stations: Infrabel operational points, published under CC0.
- Live boards: community-run [iRail](https://api.irail.be/).
- Constraint: confirm the license for returned live railway data before public publication.


## Other providers

SDP, CFV3V, PFT/TSP, Stoomcentrum Maldegem, and Rail Rebecq Rognon require new providers. Urban metro/tram systems are outside the current heavy-rail completion gate.
