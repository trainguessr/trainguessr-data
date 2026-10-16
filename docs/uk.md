# United Kingdom

## Current providers

- **Category:** `uk_national_rail`
- **Current nodes:** 2,609
- **Runtime:** National Rail Darwin, with Huxley2 fallback
- **Station ID:** CRS code
- **Station source:** UK railway station catalogue used by the generator

## Generate

```bash
python3 gen/uk.py
```

Use `--cache` to reuse the cached station JSON.

The current category covers National Rail. Northern Ireland Railways, heritage/private railways, Underground, metro, subway, and tram systems need separate providers or modes.

Reviewed exclusions are in `../overrides/exclusions/uk.json`.

## Other providers

Northern Ireland Railways, heritage/private railways, Underground, metro, subway, and tram systems need separate providers or modes.

## Terms

Keep the station-data attribution chain and ODbL obligations. Production Darwin use requires the deployer's own Rail Data Marketplace access and terms. Do not rely on the public Huxley2 demo for production. See `../ACKNOWLEDGMENTS.md`.
