# Norway

## Current providers

- **Category:** `norway_all`
- **Current nodes:** 367
- **Runtime:** Entur Journey Planner
- **Station source:** Entur National Stop Register
- **Runtime ID:** NSR stop-place ID

## Generate

```bash
python3 -m gen.countries norway
```

For an offline rebuild from a saved Entur response:

```bash
python3 -m gen.countries norway --input path/to/stop-places.json
```

The generator keeps provider records marked as active rail stops. Reviewed foreign-station exclusions are in `trainguessr-data/overrides/exclusions/norway.csv`; supporting evidence is in [`review/norway/`](../docs/review/norway).

Inactive or historical sites are not added just because a physical station still exists. Metro and light rail are separate modes.

## Other providers

Metro and light rail need a separate provider or mode.

## Terms

Entur requires a meaningful `ET-Client-Name` header. Include Entur attribution and follow NLOD terms. See `../ACKNOWLEDGMENTS.md`.

Saved exclusions apply to source station IDs. A spelling or language change does not stop generation or change which country owns a station. The source may include foreign stations. Repeated station names are allowed.
