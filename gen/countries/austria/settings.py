"""Source locations and reviewed policy constants for Austria."""
from __future__ import annotations

import re
from zoneinfo import ZoneInfo
from common.io import ROOT


CACHE_DIR = ROOT / "cache"


AUSTRIA_CACHE = CACHE_DIR / "austria"


TEMP_CACHE = CACHE_DIR / "temp"


AUSTRIA_TEMP = TEMP_CACHE / "austria"


GEONETZ_FILTERED = AUSTRIA_CACHE / "austria_stations_filtered.json"


GEONETZ_ARCHIVE = AUSTRIA_CACHE / "GeoNetz_12-2024.zip"


GEONETZ_TEMP = AUSTRIA_TEMP / "geonetz"


DEFAULT_OEBB_OPERATOR_INDEX = CACHE_DIR / "austria-oebb-operators.sqlite"


DEFAULT_OEBB_OPERATOR_AUDIT = AUSTRIA_CACHE / "oebb-operator-index-audit.json"


GEONETZ_URL = "https://data.oebb.at/dam/jcr:d4780bb2-390e-4288-b540-dff1ae1b27ae/GeoNetz_12-2024.zip"


MVO_CATALOGUE_URL = "https://www.mobilitaetsdaten.gv.at/daten/%C3%B6sterreichweite-haltestellen"


MVO_DATASETS_URL = "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets?tagIds=&tagFilterModeInclusive=false"


MVO_METADATA_URL = "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets/{dataset_id}"


MVO_FILE_URL = "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets/{dataset_id}/{year}/file"


MVO_TOKEN_URL = "https://user.mobilitaetsverbuende.at/auth/realms/dbp-public/protocol/openid-connect/token"


SCOTTY_STOP_URL = "https://fahrplan.oebb.at/bin/ajax-getstop.exe/dn"


SCOTTY_BOARD_URL = "https://fahrplan.oebb.at/bin/stboard.exe/dn"


DEFAULT_OUTPUT = ROOT / "nodes" / "nodes-austria-oebb.json"


DEFAULT_AUDIT = AUSTRIA_CACHE / "migration-audit.json"


DEFAULT_RESOLUTION_CACHE = AUSTRIA_CACHE / "scotty-resolutions.json"


DEFAULT_MVO_CACHE = AUSTRIA_CACHE / "mvo-haltestellen.zip"


_RAIL_MASK_POSITIONS = (0, 1)  # Eisenbahn, S-Bahn


_IFOPT_RE = re.compile(r"^at[-:]([0-9]+)[-:]([0-9]+)$", re.I)


_EVA_RE = re.compile(r"@L=0*([0-9]+)@")


_SUGGESTION_RE = re.compile(
    r"(?:SLs\.)?sls\s*=\s*(\{.*?\})\s*;\s*(?:SLs\.)?showSuggestion",
    re.S,
)


_MVO_SAMPLE_RE = re.compile(
    r'href=["\']([^"\']+/sites/default/files/metadataset/sample_data/[^"\']+\.zip)["\']',
    re.I,
)


_REPLACEMENT_LINE_RE = re.compile(r"^(?:SEV(?:\s+.*)?|SV\s*\d+[A-Z]*|xxx)$", re.I)


_RAIL_LINE_RE = re.compile(
    r"^(?:S\s*\d+[A-Z]*|R\s*\d+|REX\s*\d+|RJX?\s*\d*|ICE?\s*\d*|EC\s*\d*|"
    r"EN\s*\d*|WEST\s*\d*|D(?:Z)?\s*\d*|ZB\s*\d+|CJX\s*\d+|IR\s*\d+|"
    r"NJ\s*\d+|WB\s*\d+|RB\s*\d+|RX\s*\d+|LEX\s*\d+|WVB|WHB|REB|CAT|ATB\s*\d+|STB)$",
    re.I,
)


_REVIEWED_NAMES = {
    "at:46:6625": ("Mariazell", "Mariazell Bahnhof", "Mariazell Bahnhof [in St.Sebastian]"),
    "at:47:2217": ("Mayrhofen", "Mayrhofen im Zillertal Bahnhof", "Mayrhofen Bahnhof"),
    "at:43:7371": ("St. Pölten Alpenbahnhof-Kaiserwald", "St.Pölten Alpenbahnhof-Kaiserwald"),
    "at:45:54150": ("Neukirchen am Großvenediger", "Neukirchen am Großvenediger Bahnhof"),
    "at:45:54263": ("Rettenbach im Pinzgau", "Rettenbach im Pinzgau Bahnhst"),
    "at:45:54201": ("Stuhlfelden Heilbad Burgwies", "Heilbad Burgwies", "Heilbad Burgwies Bahnhst"),
    "at:45:54358": ("Lengdorf", "Lengdorf im Pinzgau", "Lengdorf im Pinzgau Bahnhst"),
    "at:45:56408": ("Seekirchen Stadt", "Seekirchen/Wallersee Stadt", "Seekirchen/Wallersee Stadt Bahnhst"),
    "at:43:72002": ("Weitersfeld (NÖ)", "Weitersfeld im Waldviertel", "Weitersfeld im Waldviertel Bahnhof"),
    "at:46:3147": ("Wies Markt", "Wies in Stmk Markt", "Wies in Stmk Markt Bahnhof"),
    "at:42:3916": ("Dellach im Gailtal", "Dellach im Gailtal", "Dellach im Gailtal Alter Bahnhof"),
    "at:42:3915": ("Gundersheim im Gailtal", "Gundersheim im Gailtal", "Gundersheim Alter Bahnhof"),
    "at:42:6166": ("St. Daniel", "St.Daniel", "St. Daniel B111"),
    "at:42:6172": ("Kirchbach im Gailtal", "Kirchbach im Gailtal Ortsmitte", "Kirchbach (Hermagor) Ortsmitte"),
    "at:42:3918": ("Kötschach-Mauthen", "Kötschach-Mauthen Alter Bahnhof"),
    "at:42:3911": ("Rattendorf-Jenig", "Rattendorf", "Rattendorf-Jenig Alter Bahnhof"),
    "at:42:7381": ("Waidegg", "Waidegg Ortsmitte", "Waidegg Ortsmitte"),
    "at:42:3909": ("Watschig", "Watschig B111", "Watschig Alter Bahnhof"),
    "at:42:6183": ("Postran", "Postran B111", "Postran B111"),
    "at:42:6180": ("Tröpolach", "Tröpolach Gailbrücke", "Tröpolach Gailbrücke"),
    "at:43:4876": ("Stetten Fossilienwelt", "Stetten b.Korneuburg Fossilienwelt Bahnhof"),
    "at:43:6004": ("Hochschneeberg", "Hochschneeberg Bahnhof"),
    "at:43:6005": ("Hengsthütte", "Hengsthütte Bahnhst"),
    "at:43:6006": ("Baumgartner", "Baumgartner Bahnhst"),
    "at:43:6056": ("Hengsttal", "Puchberg am Schneeberg Hengsttal Bahnhst"),
    "at:43:17223": ("Pfaffenschlag", "Pfaffenschlag b.Lunz Nostalgiebahnhof"),
    "at:43:17227": ("Gasthof zur Paula", "Holzapfel Gh Zur Paula Nostalgiebahnhof"),
    "at:43:70101": ("Gaming", "Gaming Nostalgiebahnhof"),
    "at:43:70103": ("Holzapfel", "Holzapfel Nostalgiebahnhof"),
    "at:43:70104": ("Lunz am See Amonhaus", "Lunz am See Amonhaus"),
    "at:43:70106": ("Reichenau an der Rax Kurhaus", "Reichenau an der Rax Kurhaus Bahnhst"),
    "at:43:70107": ("Reichenau an der Rax Lokalbahn", "Reichenau an der Rax Bahnhof"),
    "at:43:70108": ("Hirschwang/Rax Haaberg", "Reichenau an der Rax Haaberg Bahnhof"),
    "at:43:70109": ("Hirschwang/Rax Bahnhof", "Hirschwang an der Rax Bahnhof"),
    "at:43:7437": ("Kienberg", "Kienberg/Erlauf"),
    "at:43:7917": ("Lunz am See Nostalgiebahnhof", "Lunz am See Nostalgiebahnhof"),
    "at:43:71978": ("Draisinenalm Grafensulz", "Grafensulz Draisinenalm Bahnhst"),
    "at:43:71979": ("Schletz", "Schletz Bahnhst"),
    "at:43:71980": ("Asparn an der Zaya", "Asparn/Zaya Draisinenbahnhof"),
    "at:43:71981": ("Mistelbach Interspar", "Mistelbach/Zaya Interspar Bahnhst"),
}


_REVIEWED_LIGHT_RAIL_IFOPTS = {"at:47:65344"}  # Fulpmes / Stubaitalbahn


_VIENNA = ZoneInfo("Europe/Vienna")


OEBB_RAIL_ROUTE_TYPES = {2, *range(100, 200)}


_OEBB_GTFS_REQUIRED = {"agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt"}
