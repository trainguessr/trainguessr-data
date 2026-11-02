# France

## Current providers

- **Category:** `france_sncf`
- **Current nodes:** 2,854
- **Runtime:** SNCF/Gares & Connexions with Navitia journey enrichment
- **Station source:** SNCF Gares & Connexions `gares-de-voyageurs`

## Generate

```bash
python3 -m gen.countries france
```

Use `--cache` to build from the saved SNCF source file without downloading.

The generator keeps SNCF UIC identities. Multi-UIC stations, border supplements, exclusions, and reviewed additions are explicit; one station name or location must never be used to guess another UIC.

## Audit and review data

```bash
python3 -m gen.bootstrap france --help
```

The one-time research report is written under `cache/france/`. Border and supplemental records are under `../overrides/france/`. Reviewed exclusions are in `../overrides/exclusions/france.json`.

Some Corsican, RATP/RER, Monaco, heritage, and other separately operated systems need their own provider or mode instead of being forced into `france_sncf`.

## Other providers

Corsican rail, RATP/RER-only records, Monaco, and other separately operated systems need their own provider or mode.

## Terms

SNCF station data is published under ODbL. Keep the required attribution and share-alike terms. See `../ACKNOWLEDGMENTS.md`.


## Board brand and service-label provenance

Commercial marks use explicit native `trainType`/Navitia company, category and
network labels, independently of `trainMode`. A Fluo row with `trainMode=CAR`
is still Fluo-branded; the road branch must not substitute the generic SNCF mark.
Road classification and exact rail-detail eligibility remain separate. Explicit
TER NA/HDF labels remain available even when no Navitia row matches; generic
`Train` must not replace those published regional labels.

The source's optional `trainLength` is separate from the regional brand and line.
On 2026-10-29, the captured Bordeaux G&C rows (including TER NA 866163/L42) had
`trainLength: null`. The reference Connect display's “Train court/moyen” wording
cannot be reconstructed from that absence or inferred from a train number or
coach count. No extra per-row acquisition is added for this presentation pass.

The dated 844409 occurrence checked on 2026-10-29 ran Lille Europe 20:40,
Calais-Fréthun 21:08/21:19, Boulogne-sur-Mer 21:39. It belongs to none of the
three Gare du Nord board UICs; the owner confirmed the station mix-up. Existing
native UIC/mode/line filtering remains unchanged, with a captured regression.
