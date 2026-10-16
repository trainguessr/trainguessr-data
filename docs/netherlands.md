# Netherlands

## Current providers

- **Category:** `netherlands_all`
- **Current nodes:** 397
- **Runtime and station source:** Rijden de Treinen / Dutch railway data

## Generate

```bash
python3 gen/netherlands.py
```

Use `--cache` to reuse the cached station CSV.

The current category covers the national heavy-rail station namespace. Metro and tram systems are separate.

Reviewed exclusions are in `../overrides/exclusions/netherlands.json`.

## Other providers

Metro and tram systems need a separate provider or mode.

## Terms

Rijden de Treinen station data is CC0. Its live endpoint needs suitable permission for public production use. See `../ACKNOWLEDGMENTS.md`.
