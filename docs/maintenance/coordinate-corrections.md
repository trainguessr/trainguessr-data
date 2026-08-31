# Guarded station coordinate corrections

Updated: 2026-08-28

These corrections cover duplicated or stale coordinates in upstream or
rebuilt inputs.

The generator applies a correction only when the provider ID and expected name
match. If a station is missing or renamed, generation fails for review.

## Italy

### FER

- `S05100` Bologna Borgo Panigale
  - corrected to 44.5151514, 11.2849781
  - evidence: OpenStreetMap railway station node 12294207485
- `S05995` Castenaso
  - corrected to 44.50343, 11.47214
  - evidence: OpenStreetMap railway station node 257066737
- `S05931` Cavriago S.Nicolo'
  - corrected to 44.699327, 10.523291
  - evidence: Provincia di Reggio Emilia station/accessibility coordinates
- `S05971` Zola Centro
  - corrected to 44.49252, 11.21811
  - evidence: OpenStreetMap railway station node 12294207482

### EAV

- `32` Ercolano Miglio d'Oro
  - corrected to 40.80206, 14.36150
  - evidence: OpenStreetMap railway station node 11407270275; EAV lists Miglio d'Oro separately from Ercolano Scavi
- `62` Sorrento
  - corrected to 40.62585, 14.37979
  - evidence: OpenStreetMap railway station node 11061388820
- `41` Torre Annunziata - Oplonti
  - corrected to 40.75970, 14.45100
  - evidence: OpenStreetMap railway station node 11274717577; EAV and RFI list Oplonti and Centrale separately

## Spain

- `23021` Padrón Barbanza
  - corrected to 42.7812443, -8.656552
  - evidence: current official Renfe station-data export
- `05403` Tremañes-Langreo
  - corrected to 43.527123, -5.690694
  - evidence: current official Renfe FEVE station list

The Renfe source also includes service/feed identities that are not distinct
physical passenger stations. The static timetable index includes them for trip
matching, but they are not separate playable nodes:

- `99117` Ourense Turístico -> `22100` Ourense
- `99161` Pontevedra-Turístico -> `23004` Pontevedra
- `99159` Santiago-Turístico -> `31400` Santiago de Compostela-Daniel Castelao
- `70001` Vallecas -> `70005` Vallecas

The alias mapping checks both provider ID and expected names. A source rename or
new identifier makes production generation fail so it can be reviewed.

## Heritage and low-service policy

Do not exclude a station only because it has sparse, seasonal, museum-only, or
no current timetable traffic. Keep it if it is part of an existing railway in
use. Its live timetable may be empty.
