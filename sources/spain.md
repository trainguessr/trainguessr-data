# Spain

Static source: official Renfe Data GTFS archives for Cercanías/Rodalies and high-speed/long-/medium-distance services.

Dataset pages and current archive URLs:

- <https://data.renfe.com/dataset/horarios-cercanias>
- <https://data.renfe.com/dataset/horarios-de-alta-velocidad-larga-distancia-y-media-distancia>
- <https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip>
- <https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip>

Runtime source: official Renfe GTFS-Realtime trip updates (`trip_updates.json` and `trip_updates_LD.json`).

Trips are namespaced by feed (`cercanias:` or `ld:`), while shared physical stations use their stable Renfe stop code and are merged across both feeds.

Generate both required outputs from the repository root:

```shell
python3 gen/spain.py \
  --cercanias cache/renfe-cercanias.zip \
  --long-distance cache/renfe-av-ld-md.zip
```

This writes `nodes/nodes-spain-renfe.json` and the compressed runtime index
`cache/spain.sqlite`. The application expands this compressed,
normalized database once into its local cache and queries only the requested
station rather than loading the national schedule into memory.

Reviewed 2026-08-17. Renfe publishes portal-specific public-sector reuse terms,
not a CC BY declaration. Retain `Origen de los datos: Renfe Operadora`, source
and update metadata where supplied, and do not imply Renfe endorsement.
