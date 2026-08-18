# France station supplements

`cuneo-ventimiglia.json` contains the reviewed French stations on the exceptional
Cuneo–Ventimiglia cross-border line that are missing from the current
`gares-de-voyageurs` export used by `gen/france.py`.

The `sncf_id` values are the eight-digit station codes exposed by SNCF TER
station pages. `rfi_fallback_id` is the RFI station-board ID. Runtime behavior is
SNCF-first and falls back to RFI only when SNCF does not return a usable board.

Reviewed 2026-08-17. SNCF TER's official Sud Provence-Alpes-Côte d'Azur station
list names all six stops (Breil-sur-Roya, Fontan - Saorge, Saint-Dalmas-de-Tende,
La Brigue, Tende and Vievola). The repository's cached `gares-de-voyageurs`
snapshot contains none of their names/codes, so the supplement is explicit
rather than pretending the existing generator source is complete.

The SNCF API adapter still gets first choice at runtime. A direct authenticated
`api.sncf.com` smoke test could not be performed in the maintenance environment
because no SNCF API credential was available. The reviewed RFI IDs therefore
remain a deliberate fallback, not proof that SNCF live API lacks the stops.
