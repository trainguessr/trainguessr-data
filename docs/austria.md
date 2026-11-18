# Austria

## Current providers

- **Category:** `austria_oebb`
- **Current nodes:** 1,426
- **Runtime:** ÖBB SCOTTY
- **Station sources:** ÖBB GeoNetz plus the national MVO stop dataset

## Generate

```bash
python3 -m gen.countries austria
```

The generator keeps ÖBB EVA IDs and adds reviewed MVO stations only when they can be matched safely to SCOTTY. STA generation may add optional `sta_station_id` tags to these nodes, but must not change their IDs or station count. After an MVO refresh, check that a later STA run does not replace the new Austrian station list with an older one. The October 2026 station list leaves out four reviewed heritage `Nostalgiebahnhof` records. Their old mappings are evidence only; add a station again when current provider data identifies it as a station.

Useful options:

```bash
python3 -m gen.countries austria --cache
python3 -m gen.countries austria --mvo-input path/to/mvo-haltestellen.zip --cache
python3 -m gen.countries austria --mvo-sample
```

`--cache` uses saved MVO and GeoNetz source files and does not download. A normal
refresh retains a valid existing Austrian station file when MVO is unavailable,
prints a warning that the catalogue was **not refreshed**, and exits successfully.
It does not rewrite stations, source snapshots or the last successful merge audit.
Without a valid existing file it fails. Explicit sample, local-input and offline
runs still fail on unusable inputs. An explicitly requested operator-index build
remains independent and still runs after this retention fallback.
The full MVO dataset is *not* anonymously downloadable: register manually at
<https://data.mobilitaetsverbuende.at/de/data-sets>, accept the stop-list licence,
then supply `MVO_USERNAME` and `MVO_PASSWORD` privately. The official public
sample ZIP is **not a normal production fallback**: `--mvo-sample` is an
explicit opt-in for diagnostics and does not establish full-source completeness.
Missing credentials or source access is reported clearly without
replacing the existing data.
`--cache` makes no source downloads.

`--mvo-input PATH` uses a local MVO ZIP. Set `MVO_USERNAME` and `MVO_PASSWORD` to use the authenticated MVO source when needed.

An optional ÖBB GTFS file can build an operator lookup index:

```bash
python3 -m gen.countries austria --oebb-gtfs path/to/gtfs.zip --oebb-operator-index-only
```

## Unverified candidate stations

A normal run prints `OK` after successfully publishing the verified dataset. If
MVO lists station records that do not have a checked ÖBB station ID, the
generator prints each name, IFOPT and reason. These records are not added to
the ÖBB station file until their IDs are checked. The report is saved under
`cache/austria/`.

If SCOTTY was temporarily unavailable, retry the command. For persistent gaps,
check whether each record is a separate railway station and whether
SCOTTY supplies its station ID. Save the checked mapping
(`mvo_resolutions`), existing-node alias (`mvo_aliases`), or deliberate scope
exclusion (`excluded` with operator `mvo`) in
`trainguessr-data/overrides/exclusions/austria.json`; then regenerate. Do not invent an
EVA ID or delete candidates merely because their lookup failed. The `cache/austria/migration-audit.json` file is a saved report.

Known broader coverage gaps are in
[`review/austria-dataset-coverage.json`](../docs/review/austria-dataset-coverage.json).

## Other providers

Private and regional railways that do not have a safe SCOTTY identity remain separate. The known gaps are listed in `review/austria-dataset-coverage.json`.

## Terms

GeoNetz requires ÖBB attribution under CC BY 3.0 Austria. SCOTTY is a consumer service, so public use needs suitable permission or an authorized API product. See `../ACKNOWLEDGMENTS.md`.


Swiss Formation display names can use the retained GeoNetz `plc` tag. The
reviewed Austrian representation is `81` + a six-digit zero-padded national
location, compared with Formation's `81` + five digits. Only a unique PLC/name
match is accepted. This never creates an EVA identity or proves a train join.
EVA numbers are a different namespace: Formation UIC 8101477 is Radstadt through
PLC 81001477, whereas EVA 8101477 identifies Siebenbrunn-Leopoldsdorf. The
captured source fields and collision regression live in the app tests. Graz's
unmatched legacy code is not forced into a different PLC; other native name
sources remain available. Existing nodes already retain PLC, so no regeneration
or new remote name requests are needed for these five labels.

Kleinsierning Bahnhof (`at:43:20834`) matches the physical OSM stop Haag-Kleinsierning (node 8996635674), but live SCOTTY searches under both names on 2026-11-02 did not identify that railway stop. Keep it unresolved until a native SCOTTY ID is proved. An OSM node ID cannot replace it.

Station-board checks use at most four requests at once. Only failed checks are retried, once. Progress is printed every 50 IDs. `--cache` makes no live checks.

On 2026-11-02, live checks confirmed updated names for Gaming (320239), Holzapfel (320241), Holzapfel Gh Zur Paula (320238), and Pfaffenschlag b.Lunz (320237). Weidach uses SCOTTY 8101751; the MVO platform still lists the obsolete 1240712. A checked mapping takes priority over that platform field.

These physical stops still lack a working SCOTTY identity: Kleinsierning (`at:43:20834`), Reichenau Kurhaus (`at:43:70106`), Reichenau Lokalbahn (`at:43:70107`), and Hirschwang/Rax Haaberg (`at:43:70108`). Their source records are retained for checking. Do not substitute a nearby bus stop, turn their OSM IDs into provider IDs, or exclude them just because no current board is available.


### Offline checks and the four source-only stations

`--cache` replays actual successful SCOTTY checks saved in the existing `cache/austria/scotty-resolutions.json`. A platform ID or a reviewed name alone is not a successful check. Old caches without this evidence need one online run. If checks are missing, offline generation writes its report but leaves the station file unchanged. Cached journey counts are not presented as current service.

The four real railway stops are listed in `trainguessr-data/overrides/austria-unmapped-stations.csv`, with MVO IFOPT IDs, coordinates, operator links and old rejected numbers. This list is read during generation, so these records remain in the report even without qualifying current platforms. They are not exclusions or valid ÖBB mappings. Reichenau Lokalbahn, Kurhaus and Haaberg belong to ÖGLB's Höllentalbahn; Haag-Kleinsierning belongs to Eisenbahnclub Mh.6's heritage line. Their operators publish timetables, but these sources do not supply a working SCOTTY station ID. Using those timetables in the application requires an adapter for that source, not a made-up ÖBB ID.

Austria refreshes preserve existing `sta_station_id` and `sta_station_name` fields when the ÖBB ID and IFOPT still match. A changed IFOPT stops publication instead of copying a mapping to another station. These STA fields belong to the STA generator; GeoNetz/MVO must not erase them.

Innsbruck Hbf has STA stop `66007022`: the official STA EFA arrival board
published `gid=at:47:1187` for that stop on 2026-11-05, exactly matching
ÖBB EVA `8100108`'s IFOPT. This reviewed match supplements the existing
station; it does not change the station identity or infer a crosswalk by name.
