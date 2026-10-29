# Switzerland

## Current providers

- **Category:** `switzerland_all`
- **Runtime:** search.ch stationboard / Swiss transport data
- **Station source:** Swiss/SBB open service-point data

## Generate

```bash
python3 gen/switzerland.py
```

The generator keeps current service points whose pipe-separated transport modes
include the exact `TRAIN` token, including `BUS|TRAIN` (for example Locarno FART).
It preserves the official SLOID; no UIC-to-SLOID derivation is used. Non-train or historical records need separate physical and provider evidence before inclusion.

Reviewed exclusions are in `../overrides/exclusions/switzerland.json`.

## Other providers

No extra heavy-rail provider is planned for the current train namespace. Non-train modes are separate.

## Terms

Keep the required opentransportdata.swiss/SBB attribution. Confirm suitable terms for public use of the search.ch live timetable service. See `../ACKNOWLEDGMENTS.md`.
