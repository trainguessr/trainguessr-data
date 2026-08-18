# Guarded station coordinate corrections

Updated: 2026-08-18

These corrections exist because the upstream/reconstructed generator inputs can carry duplicated or stale coordinates even when the provider identifiers are valid.

The generator applies these values only when both the expected provider ID and expected station name still match. If the station disappears or is renamed, generation fails and requires manual review rather than silently applying a stale coordinate.

## Italy

### FER

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
  - evidence: OpenStreetMap railway station node 11274717577; EAV and RFI expose Oplonti and Centrale separately

## Spain

- `23021` Padrón Barbanza
  - corrected to 42.7812443, -8.656552
  - evidence: current official Renfe station-data export
- `05403` Tremañes-Langreo
  - corrected to 43.527123, -5.690694
  - evidence: current official Renfe FEVE station list

The Renfe source also carries several service/feed identities that are not separate physical passenger stations. These remain in the static timetable index when useful for trip matching but are not separate playable nodes:

- `99117` Ourense Turístico -> `22100` Ourense
- `99161` Pontevedra-Turístico -> `23004` Pontevedra
- `99159` Santiago-Turístico -> `31400` Santiago de Compostela-Daniel Castelao
- `70001` Vallecas -> `70005` Vallecas

The alias mapping is guarded by both provider ID and expected names. A future source rename or identifier replacement makes production generation fail for review.

## Heritage / low-service policy

A railway station is not excluded merely because it has sparse, seasonal, museum-only, or currently no timetable traffic if the station is part of a railway that exists and is used. Such stations may simply produce an empty live timetable.
