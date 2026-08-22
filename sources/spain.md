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
python3 gen/spain.py
```

The generator downloads both archives into `cache/spain/`, writes
`nodes/nodes-spain-renfe.json`, and writes the normalized runtime index to
`cache/spain.sqlite`. The application opens this read-only database and
queries only the requested station rather than loading the national schedule
into memory. Use the generator's local-input options for an offline rebuild.

Reviewed 2026-08-17. Renfe publishes portal-specific public-sector reuse terms,
not a CC BY declaration. Retain `Origen de los datos: Renfe Operadora`, source
and update metadata where supplied, and do not imply Renfe endorsement.
