# Italy

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Italy | `italy_sta` | STA / südtirolmobil EFA + Info Monitor | `gen/italy.py generate sta --write-nodes` | 17 native Vinschgau nodes; exact STA IDs also augment 29 shared RFI nodes and 10 shared ÖBB nodes through explicit `sta_station_id` tags. |
| Italy | `italy_rfi` | Rete Ferroviaria Italiana / ViaggiaTreno | `gen/italy.py generate rfi` | 2,426 reviewed RFI nodes; 2,399 currently have exact reviewed ViaggiaTreno IDs. The 2026-09-22 selector has 2,434 rows: 12 source-only IDs are already handled/excluded and four reviewed nodes are currently absent from the selector. |
| Italy | `italy_fn` | Ferrovienord / Trenord | `gen/italy.py generate fn` | 111 nodes from 117 source rows; six explicit exclusions. |
| Italy | `italy_fse` | Ferrovie del Sud Est / ViaggiaTreno | `gen/italy.py generate fse` | 92 nodes from 95 source rows; 85 automatic matches, seven manual records including disused Gallipoli Porto, and three explicit non-FSE/duplicate exclusions. |
| Italy | `italy_tt` | Trentino Trasporti / legacy TrainView | `gen/italy.py generate tt` | 38 matched legacy records; runtime is disabled because the historical live endpoint is unavailable. |
| Italy | `italy_fer` | Ferrovie Emilia Romagna / PittiInfo | `gen/italy.py generate fer` | 119 nodes from 132 source rows; 13 explicit exclusions and guarded reviewed coordinates, including `S05100`, are recorded. |
| Italy | `italy_eav` | Ente Autonomo Volturno | `gen/italy.py generate eav` | 119 nodes from 126 source rows; seven explicit exclusions. |

## Generation and source notes

Italy uses one dataset for each infrastructure provider. Run the command in the last column from the repository root. Each command downloads its source, stores working files in `cache/italy/<provider>/`, validates the result, and overwrites one file in `nodes/`.

| Provider | Downloaded source | Output | Command |
| --- | --- | --- | --- |
| STA / südtirolmobil | Official EFA StopFinder plus reviewed STA station catalogue | `nodes/nodes-italy-sta.json` plus exact `sta_station_id` augmentation on shared RFI/ÖBB nodes | `python3 gen/italy.py generate sta --write-nodes` |
| RFI | [RFI arrivals and departures](https://iechub.rfi.it/ArriviPartenze/ArrivalsDepartures/Home) | `nodes/nodes-italy-rfi.json` | `python3 gen/italy.py generate rfi` |
| Ferrovienord (FN) | [Trenord real-time page](https://www.trenord.it/linee-e-orari/circolazione/tempo-reale/) | `nodes/nodes-italy-fn.json` | `python3 gen/italy.py generate fn` |
| Trentino Trasporti (TT) | [Official GTFS](https://www.trentinotrasporti.it/opendata/google_transit_extraurbano_tte.zip) | `nodes/nodes-italy-tt.json` | `python3 gen/italy.py generate tt` |
| Ferrovie Emilia Romagna (FER) | FER PittiInfo line pages | `nodes/nodes-italy-fer.json` | `python3 gen/italy.py generate fer` |
| Ente Autonomo Volturno (EAV) | [EAV train information](https://orariotreni.eavsrl.it/) | `nodes/nodes-italy-eav.json` | `python3 gen/italy.py generate eav` |
| Ferrovie del Sud Est (FSE) | OpenStreetMap and ViaggiaTreno | `nodes/nodes-italy-fse.json` | `python3 gen/italy.py generate fse` |

The FN, TT, FER, EAV, and RFI datasets contain reviewed coordinates from the committed node files. Their generators match current provider records to these reviewed records by exact ID. New provider records without reviewed coordinates stay out of the playable dataset and appear in `cache/italy/<provider>/reports/audit.csv`.

TT still uses numeric IDs from its former real-time service. The official GTFS does not publish these IDs. `gen/italy.py generate tt` keeps the IDs from `nodes/nodes-italy-tt.json` and downloads the current GTFS for source review.

FSE uses ViaggiaTreno IDs and OSM coordinates. Its unresolved records and audit are in `cache/italy/fse/reports/`. Stations served by FSE and managed by RFI are in the RFI dataset.

To review all five conservative rebuilds without changing `nodes/`, run `python3 gen/italy.py rebuild all --dry-run` after their source files exist in `cache/italy/`.

#### Interactive review

In a terminal, each Italian generator opens an interactive review of new or changed items after writing and validating its dataset.

Available decisions include entering missing coordinates, excluding a provider record, keeping a reviewed station or name, and accepting a current provider name. You can defer any item or confirm all outstanding name differences for one provider with one choice.

Decisions are stored in `overrides/exclusions/italy.json`:

- Coordinate entries are stored in `manual_stations` and are restored by later generations.
- Exclusions are stored in `excluded`.
- Name confirmations are stored in `reviews` with the source and reviewed names. A changed source record creates a new question.

Run the review queue again without downloading data:

```bash
python3 gen/italy.py review all
python3 gen/italy.py review rfi
```

Automation can disable terminal review while keeping reports and validation:

```bash
TRAINGUESSR_SKIP_REVIEW=1 python3 gen/italy.py generate rfi
```


### RFI catalogue and ViaggiaTreno maintenance

The public RFI “Monitor Arrivi/Partenze live” page embeds the same `iechub.rfi.it` selector used by the RFI generator.
A routine RFI refresh therefore does not require copying the HTML selector by hand:

```bash
python3 gen/italy.py generate rfi
```

The generator saves dated source snapshots under `cache/italy/rfi/raw/snapshots/`, normalizes the current selector into
`cache/italy/rfi/derived/stations.csv`, and writes the provider-ID delta to
`cache/italy/rfi/reports/catalog-diff.json` before the conservative reviewed rebuild. New RFI IDs are not automatically
made playable: they still require reviewed coordinates. RFI IDs absent from a new selector are retained in the reviewed
node seed until they are deliberately removed.

ViaggiaTreno station-ID review is maintained separately:

```bash
python3 gen/countries/italy/rfi_viaggiatreno_review.py
```

Its durable state is `cache/italy/rfi/viaggiatreno/progress.json`. On a fresh cache it bootstraps all existing accepted
`viaggiatreno_station_id` values from `nodes/nodes-italy-rfi.json` and seeds known temporary deferrals from
`overrides/italy-rfi-viaggiatreno-deferred.json`. An optional candidate catalogue may be placed at
`cache/italy/rfi/viaggiatreno/promotion-review.json`; it is only a review aid and is never runtime authority.

At startup the reviewer reports previous deferrals and asks whether to retry none, all, or selected entries. List mode
shows the station and the reason recorded on the previous pass. Pressing `s` defers a station again and records a new
reason. Accepted mappings require an exact `Sxxxxx` provider ID; the reviewer never derives one from an RFI ID,
coordinates, a neighbouring ViaggiaTreno code, or route order. When the queue is complete, the reviewed mappings are
written back to `nodes/nodes-italy-rfi.json`.


## Attribution and provider constraints

- RFI stations and live boards: reviewed RFI records and consumer station boards.
- Ferrovienord stations and live boards: reviewed Ferrovienord records and Trenord/ViaggiaTreno.
- FSE stations and live boards: OpenStreetMap coordinates, reviewed records, and ViaggiaTreno.
- Trentino Trasporti: official GTFS under CC BY 2.5 plus reviewed legacy IDs; its legacy live source is disabled by default.
- FER and EAV: reviewed provider records and consumer station boards.
- Constraint: the undocumented or consumer live endpoints and most provider-derived station catalogues require written permission before public publication. Keep OSM/ODbL obligations where applicable.


## Other providers

The current scope excludes new providers for these additional systems: SSIF, AMT Genova–Casella, STA/Vinschgau, Infrastrutture Venete residuals, TFT/RFT, TUA/Sangritana, Ferrovie del Gargano, Ferrotramviaria, FAL, Ferrovie della Calabria, ARST, FCE, and bounded ASTRAL/metro-like systems.


## RFI ↔ ViaggiaTreno station-ID exceptions

The RFI/ViaggiaTreno bridge is intentionally fail-closed. A station receives a `viaggiatreno_station_id` only when an
exact provider-native `Sxxxxx` identity has been established. RFI IDs, names, coordinates, neighbouring ViaggiaTreno
IDs, service order, and arithmetic sequences are not substitutes for provider evidence.

Known exceptions that were investigated and are deliberately left unmapped:

- **Cansano (`3181`)**
  - **Status:** unresolved intentionally.
  - **Reason:** no independent ViaggiaTreno station identity has been established. `S08907` is the provider-native ID
    observed for the distinct Cansano Ocriticum station (`3256`), opened in 2023, and must not be reused for Cansano.
  - **Action:** leave Cansano unmapped until an exact provider-native ViaggiaTreno response establishes an identity.

- **Germagnano–Ceres: Funghera (`5168`), Traves (`5169`), Losa (`5170`), Pessinetto (`5171`), Mezzenile (`5172`),
  and Ceres (`5173`)**
  - **Status:** current RFI/Trenitalia passenger service exists, but usable ViaggiaTreno identities were unavailable
    during the September 2026 review.
  - **Reason:** RFI publishes the reopened Germagnano–Ceres services and their calls, but the corresponding trains could
    not be opened through the ViaggiaTreno interfaces used for the cross-provider bridge. Germagnano itself is
    `S00096`; that does not establish any subsequent `Sxxxxx` value. `S00097` is independently known to be Torino Corso
    Grosseto, demonstrating why numeric extrapolation is invalid.
  - **Action:** leave these six stations unmapped. Revisit when ViaggiaTreno exposes a provider-native journey/station
    response. Do not infer IDs from route order or neighbouring codes.
  - **Evidence:** RFI Ceres board:
    `https://prm.rfi.it/qo_prm/QO_Partenze_SiPMR.aspx?Id=22164706&lin=&dalle=00.00&alle=2.59&ora=00.00&guid=ffc4b7f8-72e5-4134-9f12-1d2bb821b7a9`.

- **Northern Ferrovia Centrale Umbra: La Dogana (`5413`) and San Giustino (`5414`)**
  - **Status:** unresolved while the Città di Castello–Sansepolcro rail section is closed.
  - **Reason:** current advertised connections over the closed section are replacement buses, so they do not provide a
    current ViaggiaTreno train `fermate[]` specimen from which these two missing IDs can be established. Other stations
    on the section may retain IDs that were independently reviewed from historical/provider evidence; the closure does
    not invalidate an already proven provider ID.
  - **Action:** leave these two unresolved and recheck after rail passenger service returns. Do not turn replacement-bus
    stop identities into ViaggiaTreno railway-station identities.
  - **Evidence:** contemporary reopening report:
    `https://www2.saturnonotizie.it/news/read/209739/treni-sansepolcro.html`.

- **San Michele di Pagana (`3207`)**
  - **Status:** no current ordinary passenger service and no current ViaggiaTreno identity established.
  - **Reason:** the station is not available through a current provider-native train/station specimen suitable for this
    bridge.
  - **Action:** leave unmapped unless ViaggiaTreno later supplies an exact identity.

- **Santa Bibiana (`646`)**
  - **Status:** outside the current Trenitalia/RFI passenger-service context used by this bridge.
  - **Reason:** no applicable provider-native ViaggiaTreno railway-station identity was established during review.
  - **Action:** leave unmapped; do not create a cross-provider identity from name or geography.

- **Palermo Politeama (`3261`)**
  - **Status:** no usable current ViaggiaTreno train call established during review.
  - **Reason:** the station/extension was not exposed as a provider-native ViaggiaTreno call from which an exact
    `Sxxxxx` identity could be established.
  - **Action:** leave unmapped until an operating ViaggiaTreno journey or station response provides the identity.


- **Lercara Diramazione (`2595`)**
  - **Status:** deferred.
  - **Reason:** operating point with no passenger trains stopping during review.
  - **Action:** retry only if service patterns change or a provider-native VT call becomes available.

- **FCU stations removed from passenger service in 2017: Baucca-Garavelle (`5420`), Montecorona (`5429`),
  Canoscio-Fabbrecce (`5422`), Fratta Todina (`5446`), Pian di Porto (`5448`), Cesi (`5267`), and San Martino in
  Campo (`5440`)**
  - **Status:** deferred.
  - **Reason:** these stations were recorded as removed from passenger service in the 2017 FCU changes during review.
  - **Action:** keep unmapped unless a later provider-native VT specimen establishes a current identity.

- **FCU stations without current traffic during the 2026 review: San Bartolomeo-Resina (`5433`), Collevalenza
  (`5450`), Ilci (`5447`), and Borgo Rivo (`5457`)**
  - **Status:** deferred.
  - **Reason:** no current train traffic from which to establish a provider-native VT identity.
  - **Action:** retry when passenger service returns.

- **Todi Ponte Rio (`5386`)**
  - **Status:** deferred.
  - **Reason:** recorded as removed from passenger service in 2017 during review.
  - **Action:** keep unmapped unless current provider-native evidence appears.

- **Palermo Maredolce (`2313`)**
  - **Status:** deferred.
  - **Reason:** without passenger traffic since 2020 during the review period.
  - **Action:** retry if passenger service resumes.

- **San Gottardo (Udine) (`5174`)**
  - **Status:** deferred.
  - **Reason:** no train traffic during infrastructure works at review time.
  - **Action:** explicitly retry after reopening; a temporary lack of traffic is not evidence for any guessed VT ID.

The tracked deferral seed mirrors these known exceptions so a fresh cache does not lose the research. Deferral is not a
permanent rejection: the integrated reviewer can present any or all deferred stations again on demand. Candidate
mappings elsewhere must not be promoted merely because names or coordinates are plausible.

## Guarded coordinate corrections

### FER

- `S05100` Bologna Borgo Panigale
  - corrected to 44.5151514, 11.2849781
  - evidence: OpenStreetMap railway station node 12294207485
- `S05995` Castenaso
  - corrected to 44.50343, 11.47214
  - evidence: OpenStreetMap railway station node 257066737
- `S05931` Cavriago S.Nicolo'
  - corrected to 44.699327, 10.523291
  - evidence: Provincia di Reggio Emilia station/accessibility coordinates
- `S05971` Zola Centro
  - corrected to 44.49252, 11.21811
  - evidence: OpenStreetMap railway station node 12294207482

### EAV

- `32` Ercolano Miglio d'Oro
  - corrected to 40.80206, 14.36150
  - evidence: OpenStreetMap railway station node 11407270275; EAV lists Miglio d'Oro separately from Ercolano Scavi
- `62` Sorrento
  - corrected to 40.62585, 14.37979
  - evidence: OpenStreetMap railway station node 11061388820
- `41` Torre Annunziata - Oplonti
  - corrected to 40.75970, 14.45100
  - evidence: OpenStreetMap railway station node 11274717577; EAV and RFI list Oplonti and Centrale separately
