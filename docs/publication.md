# Publishing TrainGuessr station data

**Do not equate successful generation with redistribution permission.** See
[`source-terms.json`](source-terms.json) for a conservative per-category source
lineage and status; consult [`ACKNOWLEDGMENTS.md`](../ACKNOWLEDGMENTS.md) and
upstream licences before public distribution. An `open_license_reported` entry
is not a legal clearance certificate. Generated runtime indexes under `cache/`
may embed licensed GTFS contents and must be reviewed separately from nodes.

The repository declares its curated database under ODbL 1.0 to the extent
upstream rights allow. The [licence URI](../LICENSE) and the UK Trainline
attribution chain must accompany publicly distributed derivative databases.
A public application using derived content may also require an attribution
notice. Runtime API access agreements are separate from database copyright.

## Release checklist

1. Confirm every *changed* dataset's source terms (and whether OSM/Trainline
   crosswalks have entered its published fields); record primary provider,
   snapshot origin/date, transformations, and required credit.
2. Build using the country's official inputs. Require `OK | nodes` and exit 0;
   no unresolved station review may be bypassed. Check station file changes,
   exclusions, and the source-vs-reviewed station inventory. A provider's
   absence does not automatically invalidate an independently reviewed node.
3. Validate the station corpus and relevant provider tests. Build the Renfe/FGC
   SQLite indexes as deployable artifacts **from the same feed snapshot**;
   station JSON alone is not a complete Spanish deployment. The generator
   rolls back paired station/index outputs on handled exceptions, but a crash or
   concurrent deployment can still expose an inconsistent pair; deploy them as
   one versioned release.
4. Publish one compatible set of node files and runtime indexes, with licence,
   attribution, source revision and retention policy. Do not upload private
   `.env-secret`, `.envrc`, raw credential-bearing captures or partner tokens.

Station-file checks catch invalid or repeated IDs, but cannot find stations
missing from a provider download. Each generator must compare the downloaded
provider IDs with the station list and report missing records. A claim that a
country list is complete needs a current official station list. The current
snapshot has 22,699 stations; a missing saved source cannot prove full
coverage.

Trainline `stations.csv` is an external ODbL database. Use a pinned source copy
for offline *review candidates* only; no machine-generated cross-provider ID
should silently become runtime authority or get copied into released nodes.
