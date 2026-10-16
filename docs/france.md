# France

## Current providers

- **Category:** `france_sncf`
- **Current nodes:** 2,854
- **Runtime:** SNCF/Gares & Connexions with Navitia journey enrichment
- **Station source:** SNCF Gares & Connexions `gares-de-voyageurs`

## Generate

```bash
python3 gen/france.py
```

Use `--cache` to reuse a recent SNCF download. The normal cache limit is seven days.

The generator keeps SNCF UIC identities. Multi-UIC stations, border supplements, exclusions, and reviewed additions are explicit; one station name or location must never be used to guess another UIC.

## Audit and review data

```bash
python3 gen/france.py --audit --help
```

Large reconciliation results are in [`review/france-reconciliation.json`](review/france-reconciliation.json). Border and supplemental records are under [`review/france/`](review/france/). Reviewed exclusions are in `../overrides/exclusions/france.json`.

Some Corsican, RATP/RER, Monaco, heritage, and other separately operated systems need their own provider or mode instead of being forced into `france_sncf`.

## Other providers

Corsican rail, RATP/RER-only records, Monaco, and other separately operated systems need their own provider or mode.

## Terms

SNCF station data is published under ODbL. Keep the required attribution and share-alike terms. See `../ACKNOWLEDGMENTS.md`.
