# Netherlands

## Current providers

- **Category:** `netherlands_all`
- **Current nodes:** 397
- **Runtime and station source:** Rijden de Treinen / Dutch railway data

## Generate

```bash
python3 -m gen.countries netherlands
```

Use `--cache` to build from the saved station CSV without downloading.

The current category covers the national heavy-rail station namespace. Metro and tram systems are separate.

Reviewed exclusions are in `trainguessr-data/overrides/exclusions/netherlands.json`.

## Other providers

Metro and tram systems need a separate provider or mode.

## Terms

Rijden de Treinen station data is CC0. Its live endpoint needs suitable permission for public production use. See `../ACKNOWLEDGMENTS.md`.
