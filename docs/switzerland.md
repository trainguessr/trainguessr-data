# Switzerland

## Current providers

- **Category:** `switzerland_all`
- **Current nodes:** 1,697
- **Runtime:** search.ch stationboard / Swiss transport data
- **Station source:** Swiss/SBB open service-point data

## Generate

```bash
python3 gen/switzerland.py
```

The generator keeps current service points marked for train service. Non-train or historical records need separate physical and provider evidence before inclusion.

Reviewed exclusions are in `../overrides/exclusions/switzerland.json`.

## Other providers

No extra heavy-rail provider is planned for the current train namespace. Non-train modes are separate.

## Terms

Keep the required opentransportdata.swiss/SBB attribution. Confirm suitable terms for public use of the search.ch live timetable service. See `../ACKNOWLEDGMENTS.md`.
