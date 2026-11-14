# Denmark

## Current providers

- **Category:** `denmark_all`
- **Current nodes:** 563
- **Runtime:** Rejseplanen API 2.0
- **Station source:** Rejseplanen Labs GTFS

## Generate

Set `REJSEPLANEN_API_KEY`, then run:

```bash
python3 -m gen.countries denmark
```

Useful modes:

```bash
python3 -m gen.countries denmark --cache
```

`--cache` uses the saved GTFS file and makes no network calls. To check a live
station board, run without `--cache` and add `--validate-live`; this optional
check needs `REJSEPLANEN_API_KEY`.

The dataset includes ordinary rail, S-tog, and the railway-like Letbane services already supported by the provider. Metro is kept outside this category for now.

Reviewed exclusions are in `trainguessr-data/overrides/exclusions/denmark.json`.

## Other providers

Metro stays outside `denmark_all` for now.

## Terms

Rejseplanen Labs access needs approval and an API key. Follow its quota and use terms. See `../ACKNOWLEDGMENTS.md`.
