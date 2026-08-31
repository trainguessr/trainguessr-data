# France

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| France | `france_sncf` | SNCF API/Navitia-compatible station namespace | `gen/france.py`; `gen/france.py --audit` | 2,846 nodes from the current 2,782-record SNCF export, 52 exact current SNCF Reseau passenger supplements (including one corrected Fontanil UIC), nine exact-UIC historical passenger supplements, and six reviewed Cuneo-Ventimiglia supplements, after three explicit API-identity exclusions. The physical audit records 20 deferred RATP/RER records, six separate-provider candidates, one Monaco scope gap, and seven unresolved SNCF/Occitanie candidates. Corsica CFC is a separate 65-stop `new_provider_needed` system. |

## Generation and source notes

SNCF exports its stations as open data in a JSON file [here](https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe%2FBerlin).

These station IDs are then used in the SNCF API, which requires an API key. Get a free API key from the [SNCF Numerique](https://numerique.sncf.com/) website.

Run `python3 gen/france.py` from the repository root. The generator refreshes a
cache older than seven days; use `--refresh` to force a download. The API key is
not needed to generate stations, only for live departures.

The reviewed French section of Cuneo-Ventimiglia is supplemented from
`docs/review/france/cuneo-ventimiglia.json`. SNCF is the primary live source;
the recorded RFI board IDs are explicit fallbacks.

The physical candidate audit accepts repeatable `--osm-input` captures and
writes `docs/review/france-reconciliation.json`; it does not promote unmatched OSM
UIC values into runtime station IDs without provider verification. Exact UICs
marked as passenger by the official SNCF Reseau `liste-des-gares` cross-check
are generated from `docs/review/france/liste-des-gares-supplement.json`, which also
contains nine explicitly historical passenger-ID additions backed by the
official `frequentation-gares` register and the corrected current Fontanil UIC
crosswalk.


## SNCF export checkpoint

The official SNCF Gares & Connexions export used by `gen/france.py` was
refreshed on 2026-08-27:

- 2,782 records were returned;
- every record had a name, geographic position, and at least one UIC code;
- 11 records contain multiple UIC codes, with no duplicate UIC across records;
- the generated output contains 2,846 nodes: 2,779 export records after the
  three explicit API-identity exclusions, plus 52 reviewed SNCF Reseau
  infrastructure supplements, nine historical Gares & Connexions supplements,
  and the six reviewed Cuneo-Ventimiglia supplements below.

The SNCF source conversion covers the complete official export. A separate
physical audit covers no-current-service or dismantled sites because the SNCF
export is a current passenger-station source, not a historical infrastructure
register.

`cuneo-ventimiglia.json` contains the reviewed French stations on the exceptional
Cuneo–Ventimiglia cross-border line that are missing from the current
`gares-de-voyageurs` export used by `gen/france.py`.

The `sncf_id` values are the eight-digit station codes listed on SNCF TER
station pages. `rfi_fallback_id` is the RFI station-board ID. Runtime behavior is
SNCF-first and falls back to RFI only when SNCF does not return a usable board.

SNCF TER's official Sud Provence-Alpes-Côte d'Azur station list names all six
stops (Breil-sur-Roya, Fontan - Saorge, Saint-Dalmas-de-Tende,
La Brigue, Tende and Vievola). The repository's cached `gares-de-voyageurs`
snapshot contains none of their names/codes, so the supplement is explicit
rather than pretending the existing generator source is complete.

The SNCF API adapter gets first choice at runtime. A direct authenticated
`api.sncf.com` smoke test could not be run in the test environment
because no SNCF API credential was available. The reviewed RFI IDs therefore
are a deliberate fallback, not proof that SNCF live API lacks the stops.

## Chemins de fer de la Corse

CFC is not represented by the SNCF export. The current official operator pages
state that the Corsican network has 16 stations and 49 halts, is dedicated to
passenger trains, and has current 2026 timetable PDFs:

- <https://cf-corse.corsica/les-gares/>
- <https://cf-corse.corsica/plan-du-reseau/>
- <https://cf-corse.corsica/horaires/>

The official site search did not show a GTFS or API result, and the reviewed
pages list no stable native station identifiers. CFC is therefore a
`new_provider_needed` system with 65 documented passenger stops. No OSM IDs,
guessed SNCF IDs, or PDF-derived pseudo-identifiers were added to
`france_sncf`.

## Physical audit checkpoint

`gen/france.py --audit` compares bounded OpenStreetMap/Overpass captures with
the generated SNCF output. The five captures used for the 2026-08-31 checkpoint
are listed in `docs/review/france-reconciliation.json`; they are disposable
external inputs under `cache/france/audit/` and are not treated as provider data.

The exact capture files, areas, and query are reproducible with:

```bash
python3 gen/reconcile/france_capture.py --refresh
```

| Capture file | Overpass bounding box (`south,west,north,east`) |
| --- | --- |
| `cache/france/audit/trainguessr-france-osm-sw.json` | `41.3,-5.2,46.3,2.25` |
| `cache/france/audit/trainguessr-france-osm-se.json` | `41.3,2.25,46.3,9.7` |
| `cache/france/audit/trainguessr-france-osm-ne.json` | `46.3,2.25,51.2,9.7` |
| `cache/france/audit/trainguessr-france-osm-nw-n.json` | `48.75,-5.2,51.2,2.25` |
| `cache/france/audit/trainguessr-france-osm-nw-s2.json` | `47.5,-5.2,48.75,2.25` |

Each area uses the following query, with `{bbox}` replaced by its table row:

```text
[out:json][timeout:180];(nwr["railway"~"^(station|halt|stop)$"]({bbox});nwr["disused:railway"~"^(station|halt|stop)$"]({bbox});nwr["abandoned:railway"~"^(station|halt|stop)$"]({bbox}););out center tags;
```

The helper writes a file only after a successful JSON response containing an
`elements` array; failed network requests are reported and never replaced with
fabricated captures.

- 36,311 captured OSM elements were deduplicated;
- 2,480 French `train=yes` `railway=station|halt` elements were selected;
- 2,183 distinct seven-digit UIC stems beginning with `87` were found;
- 2,088 stems matched an existing SNCF output ID or `further_ids`;
- 95 unmatched stems are explicit audit candidates.

The 95 candidates are classified as 61 existing-provider additions, 20 deferred
RATP/RER secondary-mode records, six separate-provider records (Chemins de fer
de Provence, TTDA, ATTCV, CFHA, and CFC), one Monaco scope/provider gap, and 7
unresolved SNCF/Occitanie records. The 51 direct current additions use exact
UICs marked `voyageurs=O` by SNCF Reseau. One further current addition corrects
the Fontanil UIC from an older OSM/frequency value to the current official
`87561143`. Nine further additions use exact UICs with
positive historical passenger counts from the SNCF Gares & Connexions
`frequentation-gares` register; all have current OSM physical station evidence.
Six of the deferred RATP/RER records were identified through the current
Île-de-France Mobilités station registry and GTFS-aligned stop dataset because
their OSM captures did not carry operator tags: `8775808` (IDFM station 439,
RER A), `8775834` (597, RER A), `8775870` (790, RER B), `8775871` (287, RER B),
`8775883` (429, RER B), and `8775886` (401, RER B). Their stable
`IDFM:monomodalStopPlace:*` IDs are kept in the audit evidence, but no old
SNCF UIC suffix is promoted.

The seven unresolved outcomes are `8714202` Bricon, `8731350` Roye,
`8764124` Eygurande-Merlines, `8773232` Puy-Guillaume, `8775322` Berre,
`8776587` Villeneuve-lès-Avignon, and `8778433` Le Boulou-Le Perthus. Their
current SNCF infrastructure records are non-passenger records; the available
evidence does not safely show a current SNCF runtime identity or a
dismantled physical site. No candidate was added or excluded solely
from OSM evidence.

The 51 current additions use the official SNCF Reseau `liste-des-gares` export dated
2024-03-28 (`voyageurs=O`) for the exact eight-digit UIC and coordinates, with
the current OSM capture supplying the physical station corroboration. The
 dated infrastructure register is not interpreted as proof of current train
 service; stations with no current service are valid physical-site entries.

The nine historical additions use the official `frequentation-gares` export's
2015-2024 passenger counts and the exact eight-digit UIC. The frequency dataset
is historical evidence rather than a current service feed; the source file
keeps its year-by-year counts. Eleven candidate stems had historical
passenger records in total: nine were historical-only additions, one was
the Fontanil UIC correction below, and Monaco is a provider gap.

The historical frequency UIC `87565143` for Fontanil is not
promoted. The current SNCF Reseau infrastructure register lists `87561143`
for the same named and located stop, and that current official UIC is the one
written to the output.

## Attribution and provider constraints

- Stations: SNCF Gares & Connexions `gares-de-voyageurs`, with a reviewed Cuneo-Ventimiglia supplement.
- Live boards: SNCF API / Navitia; reviewed border stations may fall back to RFI boards.
- Separate provider evidence: current Chemins de fer de la Corse operator schedules and network pages.
- Île-de-France secondary-mode cross-check: Île-de-France Mobilités station registry and GTFS-aligned stop dataset, under Licence Ouverte/ODbL as published by the datasets.
- Physical discovery audit: OpenStreetMap contributors through bounded Overpass captures, under ODbL.
- Attribution: Source: SNCF Gares & Connexions Open Data. Station data is ODbL.
- Constraint: keep ODbL attribution/share-alike and confirm current SNCF API and underlying coverage terms.


## Other providers

Chemins de fer de la Corse and other separately operated physical systems in the France reconciliation require new providers. RATP/RER secondary-mode records are outside `france_sncf` where SNCF identity is not valid.
