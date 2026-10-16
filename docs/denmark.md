# Denmark

## Current providers

- **Category:** `denmark_all`
- **Current nodes:** 563
- **Runtime:** Rejseplanen API 2.0
- **Station source:** Rejseplanen Labs GTFS

## Generate

Set `REJSEPLANEN_API_KEY`, then run:

```bash
python3 gen/denmark.py
```

Useful modes:

```bash
python3 gen/denmark.py --cache
python3 gen/denmark.py --offline
```

`--cache` reuses the local GTFS file. `--offline` uses only the cached GTFS and makes no network/API calls.

The dataset includes ordinary rail, S-tog, and the railway-like Letbane services already supported by the provider. Metro is kept outside this category for now.

Reviewed exclusions are in `../overrides/exclusions/denmark.json`.

## Other providers

Metro stays outside `denmark_all` for now.

## Terms

Rejseplanen Labs access needs approval and an API key. Follow its quota and use terms. See `../ACKNOWLEDGMENTS.md`.
