# Sweden

## Current providers

- **Category:** `sweden_all`
- **Current nodes:** 832
- **Runtime:** Trafiklab ResRobot
- **Station source:** Trafiklab/Samtrafiken NeTEx stop register

## Generate

Set `TRAFIKLAB_API_KEY_STOPS`, then run:

```bash
python3 gen/sweden.py
```

Use `--cache` to reuse the downloaded NeTEx ZIP and extracted XML.

The generator streams stop places directly from the XML. It keeps Swedish `rail` and `metro` records with national `740...` IDs and rejects foreign IDs. Reviewed exclusions are in `../overrides/exclusions/sweden.json`.

Ordinary tram expansion is outside the current category.

## Other providers

Ordinary tram systems are outside the current category.

## Terms

The documented station datasets are CC0. Use registered Trafiklab keys, follow quotas, and do not imply endorsement. See `../ACKNOWLEDGMENTS.md`.
