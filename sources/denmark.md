# Denmark

Static source: official Rejseplanen Labs GTFS Schedule (Static), refreshed by Rejseplanen on an approximately two-week cycle. The current feed URL is <https://www.rejseplanen.info/labs/GTFS.zip>.

Access is not anonymous. Request access at
<https://labs.rejseplanen.dk/hc/requests/new?ticket_form_id=17536468593565>,
then sign in to Labs and request approved access to the static feed and API. Generate the station data from the repository root with:

```shell
python3 gen/denmark.py
```

The generator downloads the static archive into `cache/denmark/`, where all downloaded source material is kept. It writes the playable station list to `nodes/nodes-denmark.json` and smoke-tests both API board directions using `REJSEPLANEN_API_KEY`.

Runtime source: Rejseplanen API 2.0 departure/arrival boards. An access key is required. Confirm the applicable non-commercial/commercial quota before public deployment.

`gen/denmark.py` filters GTFS trips to railway route types, normalizes zero-padded numeric stop IDs to the seven-digit API IDs, and keeps only stops served by those trips. The generated IDs are smoke-tested against the issued Rejseplanen access before publication.
