# Finland

## Current providers

- **Category:** `finland_all`
- **Current nodes:** 222
- **Runtime and station source:** Fintraffic Digitraffic
- **Runtime ID:** Fintraffic station short code

## Generate

```bash
python3 gen/finland.py
```

To rebuild from a saved metadata response:

```bash
python3 gen/finland.py --input path/to/stations.json
```

The normal dataset includes current passenger stations plus a small reviewed set of physical station sites without current passenger traffic.

## Audit

Physical reconciliation is separate from normal generation:

```bash
python3 gen/finland.py --audit --help
```

The full result is in [`review/finland-reconciliation.json`](review/finland-reconciliation.json). Manual retained stations are in `../overrides/finland-review.json`.

Helsinki metro and tram are not Fintraffic railway identities and need a separate provider.

## Other providers

Helsinki metro and tram need a separate provider.

## Terms

Digitraffic data is CC BY 4.0. Keep the source, licence, and modification notice. See `../ACKNOWLEDGMENTS.md`.
