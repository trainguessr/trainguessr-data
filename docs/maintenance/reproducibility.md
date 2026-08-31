# Repository maintenance and reproducibility

## Directory contract

`cache/` has files that can be downloaded or generated again and is ignored.
`nodes/` has the playable generated output.
`docs/` has guides plus machine-readable evidence and
reconciliation ledgers.
`gen/` has one public country entrypoint per supported country. Complex code is
under `gen/common/`, `gen/countries/`, or `gen/reconcile/`.
`overrides/` has only reviewed settings that change generated output.
`tests/` has committed regression tests.

## Public generator entrypoints

Run `python3 gen/<country>.py` for normal generation. For Finland, France, and
Germany, run `python3 gen/<country>.py --audit` for physical/provider
reconciliation.

Italy uses one dispatcher:

```bash
python3 gen/italy.py generate all
python3 gen/italy.py generate rfi
python3 gen/italy.py review all
python3 gen/italy.py rebuild all --dry-run
```

Provider-specific Italian code is under `gen/countries/italy/`.

## Reviewed decisions

Put exclusions, renames, coordinate corrections, aliases, and manually reviewed
provider mappings under `overrides/`. Each record must check station identity so
an upstream rename or ID change cannot silently apply an old decision to another
station.

Put large discovery and reconciliation results under `docs/review/`. Generators
may read reviewed source and evidence records there, but code must use only
explicit terminal statuses.

## Breaking upstream changes

Generators must validate required source fields and fail on incompatible schema
changes. A source refresh must not silently shrink the catalogue because a field
disappeared, an endpoint returned the wrong representation, or a timetable
window contained no service.

Stable TrainGuessr/provider identities must not change when upstream arrays are
reordered. Set canonical IDs and aliases explicitly.

## Fresh-clone expectation

A clean clone without `cache/` must:
1. import and compile all generators and tests;
2. validate all committed `nodes/`;
3. run the normal test suite without failures;
4. skip only tests that need a cache download, credentials, or opt-in live
   access.

Live rebuilds may need credentials or network access. The country page must list
the exact command, input, and blocker.
