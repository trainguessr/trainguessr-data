# Austria

## Current providers

- **Category:** `austria_oebb`
- **Current nodes:** 1,416
- **Runtime:** ÖBB SCOTTY
- **Station sources:** ÖBB GeoNetz plus the national MVO stop dataset

## Generate

```bash
python3 gen/austria.py
```

The generator keeps ÖBB EVA IDs and adds reviewed MVO stations only when they can be matched safely to SCOTTY.

Useful options:

```bash
python3 gen/austria.py --cache
python3 gen/austria.py --offline --mvo-input cache/austria/mvo-haltestellen.zip
```

`--mvo-input PATH` uses a local MVO ZIP. Set `MVO_USERNAME` and `MVO_PASSWORD` to use the authenticated MVO source when needed.

An optional ÖBB GTFS file can build an operator lookup index:

```bash
python3 gen/austria.py --oebb-gtfs path/to/gtfs.zip --oebb-operator-index-only
```

## Review data

Known coverage gaps and review results are in [`review/austria-dataset-coverage.json`](review/austria-dataset-coverage.json). Reviewed exclusions are in `../overrides/exclusions/austria.json`.

## Other providers

Private and regional railways that do not have a safe SCOTTY identity remain separate. The known gaps are listed in `review/austria-dataset-coverage.json`.

## Terms

GeoNetz requires ÖBB attribution under CC BY 3.0 Austria. SCOTTY is a consumer service, so public use needs suitable permission or an authorized API product. See `../ACKNOWLEDGMENTS.md`.
