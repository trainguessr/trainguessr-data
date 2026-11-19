# Switzerland

## Current providers

- **Category:** `switzerland_all`
- **Runtime:** search.ch stationboard / Swiss transport data
- **Station source:** Swiss/SBB open service-point data

## Generate

```bash
python3 -m gen.countries switzerland
```

The generator keeps current service points whose pipe-separated transport modes
include the exact `TRAIN` token, including `BUS|TRAIN` (for example Locarno FART).
It preserves the official SLOID; no UIC-to-SLOID derivation is used. Non-train or historical records need separate physical and provider evidence before inclusion.

Platform sectors: the generator also downloads SBB's `sektortafel` (sector signs,
cached as `cache/switzerland/sektortafel.json`) and tags each station with
`sbb_platform_sectors`, e.g. `8:ABCDEFGH;49:GHJKLMN` (customer track → letters along
the platform). Letters run alphabetically; a skipped letter (Bern 49 has no I) is
kept only when a sign joins the two letters. Gaps without such a sign, signs joining
non-neighbouring letters, single sectors and non-letter values drop that track.

Reviewed exclusions are in `trainguessr-data/overrides/exclusions/switzerland.json`.

## Other providers

No extra heavy-rail provider is planned for the current train namespace. Non-train modes are separate.

## Terms

Keep the required opentransportdata.swiss/SBB attribution. Confirm suitable terms for public use of the search.ch live timetable service. See `../ACKNOWLEDGMENTS.md`.
