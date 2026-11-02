# Finland

## Current providers

- **Category:** `finland_all`
- **Current nodes:** 222
- **Runtime and station source:** Fintraffic Digitraffic
- **Runtime ID:** Fintraffic station short code

## Generate

```bash
python3 -m gen.countries finland
```

To rebuild from a saved metadata response:

```bash
python3 -m gen.countries finland --input path/to/stations.json
```

The dataset includes valid Finnish station and stopping-point records from Fintraffic, including records with no current passenger traffic. The generator reports these records and keeps their provider IDs.

## Audit

Additional station checks are separate from normal generation:

```bash
python3 -m gen.bootstrap finland --help
```

The one-time research report is written under `cache/finland/`. The current station file is the reviewed station list. The small `../overrides/finland-stations.csv` file checks saved IDs and names.

Helsinki metro and tram are not Fintraffic railway identities and need a separate provider.

## Other providers

Helsinki metro and tram need a separate provider.

## Terms

Digitraffic data is CC BY 4.0. Keep the source, licence, and modification notice. See `../ACKNOWLEDGMENTS.md`.
