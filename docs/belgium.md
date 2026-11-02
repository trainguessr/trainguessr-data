# Belgium

## Current providers

- **Category:** `belgium_all`
- **Current nodes:** 604
- **Runtime:** iRail / NMBS-SNCB
- **Station source:** iRail, checked against Infrabel where needed

## Generate

```bash
python3 -m gen.countries belgium
```

iRail provides the station IDs and does not require an API key. Infrabel and OpenStreetMap are used only to check physical railway locations; they do not replace iRail IDs.

Reviewed exclusions are in `../overrides/exclusions/belgium.json`.

## Other providers

The current category covers the main NMBS-SNCB network. Tourist railways and urban metro/tram systems need separate providers.

## Terms

Infrabel operational-point data is CC0. iRail is community-run; confirm the terms for live railway data before public publication. See `../ACKNOWLEDGMENTS.md`.

Saved exclusions apply to source station IDs. A spelling or language change does not stop generation or change which country owns a station. The source may include foreign stations. Repeated station names are allowed.
