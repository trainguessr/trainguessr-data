# Italy

## Current providers

Italy has several railway providers. They share one public generator: `gen/italy.py`.

| Category | Provider | Nodes | Command |
| --- | --- | ---: | --- |
| `italy_rfi` | RFI / ViaggiaTreno | 2,426 | `python3 gen/italy.py generate rfi` |
| `italy_fn` | Ferrovienord / Trenord | 111 | `python3 gen/italy.py generate fn` |
| `italy_fse` | Ferrovie del Sud Est / ViaggiaTreno | 92 | `python3 gen/italy.py generate fse` |
| `italy_tt` | Trentino Trasporti | 38 | `python3 gen/italy.py generate tt` |
| `italy_fer` | Ferrovie Emilia Romagna | 117 | `python3 gen/italy.py generate fer` |
| `italy_eav` | Ente Autonomo Volturno | 119 | `python3 gen/italy.py generate eav` |
| `italy_sta` | südtirolmobil / STA | 17 | `python3 gen/italy.py generate sta --write-nodes` |

## Generate and review

Generate one provider or all providers:

```bash
python3 gen/italy.py generate rfi
python3 gen/italy.py generate all
```

Review saved changes without downloading again:

```bash
python3 gen/italy.py review all
python3 gen/italy.py review rfi
```

Check conservative rebuilds without replacing `nodes/`:

```bash
python3 gen/italy.py rebuild all --dry-run
```

Set `TRAINGUESSR_SKIP_REVIEW=1` when an automated run must skip the interactive review UI.

Most Italian generators compare the current provider catalogue with reviewed station records. New or changed provider records are not silently accepted. Review decisions live mainly in `../overrides/exclusions/italy.json`; guarded coordinate fixes are in `../overrides/italy-coordinate-corrections.json`.

## Important provider notes

- **RFI:** uses reviewed RFI station records. Exact ViaggiaTreno `Sxxxxx` IDs are reviewed separately; they are never derived from the RFI ID, route order, names, or nearby stations.
- **STA:** the default generation is non-destructive. Use `--write-nodes` only after review.
- **TT:** keeps legacy provider IDs, and its old live endpoint is no longer relied on by this data build.
- **FSE:** uses ViaggiaTreno IDs and reviewed physical station data. Shared RFI-managed stations stay in the RFI dataset.
- **FER, EAV, FN:** use reviewed provider records and fail for identity changes that need review.

The RFI/ViaggiaTreno review tool is:

```bash
PYTHONPATH=gen python3 gen/reconcile/italy_rfi_viaggiatreno.py
```

Temporary deferrals are stored in `../overrides/italy-rfi-viaggiatreno-deferred.json`.

## Other providers

Several smaller Italian railways still need separate providers. Do not assign them an RFI/ViaggiaTreno identity without provider evidence.

## Terms

Many Italian live sources are consumer or undocumented endpoints. Public use may need written permission. Keep OSM/ODbL obligations where used. See `../ACKNOWLEDGMENTS.md`.
