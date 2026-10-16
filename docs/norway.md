# Norway

## Current providers

- **Category:** `norway_all`
- **Current nodes:** 367
- **Runtime:** Entur Journey Planner
- **Station source:** Entur National Stop Register
- **Runtime ID:** NSR stop-place ID

## Generate

```bash
python3 gen/norway.py
```

For an offline rebuild from a saved Entur response:

```bash
python3 gen/norway.py --input path/to/stop-places.json
```

The generator keeps active rail stop places. Reviewed foreign/cross-provider exclusions are in `../overrides/exclusions/norway.json`; supporting evidence is in [`review/norway/`](review/norway/).

Inactive or historical sites are not added just because a physical station still exists. Metro and light rail are separate modes.

## Other providers

Metro and light rail need a separate provider or mode.

## Terms

Entur requires a meaningful `ET-Client-Name` header. Include Entur attribution and follow NLOD terms. See `../ACKNOWLEDGMENTS.md`.
