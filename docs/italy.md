# Italy

## Current providers

| Country | Category | Runtime provider | Generator | Coverage |
| --- | --- | --- | --- | --- |
| Italy | `italy_rfi` | Rete Ferroviaria Italiana / ViaggiaTreno | `gen/italy.py generate rfi` | 2,426 nodes from 2,438 source rows; six French cross-border boards are handled by `france_sncf`, and six records are excluded. |
| Italy | `italy_fn` | Ferrovienord / Trenord | `gen/italy.py generate fn` | 111 nodes from 117 source rows; six explicit exclusions. |
| Italy | `italy_fse` | Ferrovie del Sud Est / ViaggiaTreno | `gen/italy.py generate fse` | 92 nodes from 95 source rows; 85 automatic matches, seven manual records including disused Gallipoli Porto, and three explicit non-FSE/duplicate exclusions. |
| Italy | `italy_tt` | Trentino Trasporti / legacy TrainView | `gen/italy.py generate tt` | 38 matched legacy records; runtime is disabled because the historical live endpoint is unavailable. |
| Italy | `italy_fer` | Ferrovie Emilia Romagna / PittiInfo | `gen/italy.py generate fer` | 119 nodes from 132 source rows; 13 explicit exclusions and guarded reviewed coordinates, including `S05100`, are recorded. |
| Italy | `italy_eav` | Ente Autonomo Volturno | `gen/italy.py generate eav` | 119 nodes from 126 source rows; seven explicit exclusions. |

## Generation and source notes

Italy uses one dataset for each infrastructure provider. Run the command in the last column from the repository root. Each command downloads its source, stores working files in `cache/italy/<provider>/`, validates the result, and overwrites one file in `nodes/`.

| Provider | Downloaded source | Output | Command |
| --- | --- | --- | --- |
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


## Attribution and provider constraints

- RFI stations and live boards: reviewed RFI records and consumer station boards.
- Ferrovienord stations and live boards: reviewed Ferrovienord records and Trenord/ViaggiaTreno.
- FSE stations and live boards: OpenStreetMap coordinates, reviewed records, and ViaggiaTreno.
- Trentino Trasporti: official GTFS under CC BY 2.5 plus reviewed legacy IDs; its legacy live source is disabled by default.
- FER and EAV: reviewed provider records and consumer station boards.
- Constraint: the undocumented or consumer live endpoints and most provider-derived station catalogues require written permission before public publication. Keep OSM/ODbL obligations where applicable.


## Other providers

The current scope excludes new providers for the additional systems documented in `docs/new-providers.md`: SSIF, AMT Genova–Casella, STA/Vinschgau, Infrastrutture Venete residuals, TFT/RFT, TUA/Sangritana, Ferrovie del Gargano, Ferrotramviaria, FAL, Ferrovie della Calabria, ARST, FCE, and bounded ASTRAL/metro-like systems.
