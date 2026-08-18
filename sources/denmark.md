# Denmark

Static source: official Rejseplanen Labs GTFS Schedule (Static), refreshed by Rejseplanen on an approximately two-week cycle.

Access is not anonymous. Request access at
<https://labs.rejseplanen.dk/hc/requests/new?ticket_form_id=17536468593565>,
then sign in to Labs and download the approved GTFS archive. Generate it with:

```shell
python3 gen/denmark.py --input cache/denmark/rejseplanen-gtfs.zip
```

Runtime source: Rejseplanen API 2.0 departure/arrival boards. An access key is required. Confirm the applicable non-commercial/commercial quota before public deployment.

`gen/denmark.py` filters GTFS trips to railway route types, then keeps only stops served by those trips. The generated GTFS stop/station ID is passed to the live API and must be smoke-tested against the issued Rejseplanen access before publication.
