"""Source locations and reviewed policy constants for Germany."""
from __future__ import annotations

from common.io import ROOT


GTFS_URL = "https://download.gtfs.de/germany/rv_free/latest.zip"


GTFS_FEED_PAGE = "https://gtfs.de/en/feeds/germany/"


DB_BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"


DB_STATION_URL = f"{DB_BASE_URL}/station/{{eva}}"


DB_PLAN_URL = f"{DB_BASE_URL}/plan/{{eva}}/{{slot}}"


DB_WILDCARD_URL = f"{DB_BASE_URL}/station/*"


BOUNDARY_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_DEU_0.json"


OSM_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


GERMANY_CACHE = ROOT / "cache" / "germany"


GTFS_ARCHIVE = GERMANY_CACHE / "rv-latest.zip"


DB_SNAPSHOT = GERMANY_CACHE / "db-stations-current.xml"


BOUNDARY_CACHE = GERMANY_CACHE / "deu.geo.json"


STALE_OSM_CACHE = GERMANY_CACHE / "osm-stale.json"


CATALOGUE = GERMANY_CACHE / "full.json"


NODES = ROOT / "nodes" / "nodes-germany.json"


AUDIT_FILE = ROOT / "docs" / "review" / "germany-reconciliation.json"


REVIEWED_STATION_OVERRIDES = ROOT / "overrides" / "germany-station-mappings.json"


DEFAULT_PLAN_SLOT = "260828/13"


REQUEST_HEADERS = {
    "Accept": "application/xml",
    "User-Agent": "TrainGuessr-data/germany-reconciliation",
}


OSM_RADIUS_METRES = 1_000.0


OSM_BATCH_SIZE = 1


OSM_REQUEST_TIMEOUT = (10.0, 120.0)


NODE_MATCH_RADIUS_METRES = 1_200.0


GENERIC_NAME_TOKENS = {
    "a",
    "am",
    "bf",
    "bhf",
    "bahnhof",
    "haltepunkt",
    "halt",
    "hbf",
    "hp",
    "station",
    "fr",
    "s",
    "u",
}


SEPARATE_PROVIDER_MARKERS = (
    "angelner dampfeisenbahn",
    "bergwerksbahn",
    "brohltalbahn",
    "dampfnostalgie",
    "dampfeisenbahn",
    "harzer schmalspurbahn",
    "ilztalbahn",
    "kandertalbahn",
    "kleinbahn",
    "mainschleifenbahn",
    "mecklenburgische baederbahn",
    "molli",
    "museumsbahn",
    "oechsle",
    "parkeisenbahn",
    "partyzug",
    "pressnitztalbahn",
    "rhoen zuegle",
    "schmalspurbahn",
    "sdg saechsische dampfeisenbahngesellschaft",
    "touristische bahnen",
    "wanderbahn",
    "zugspitzbahn",
    "verkehrsbetriebe grafschaft hoya",
    "selfkantbahn",
    "kuckucksbahnel",
    "chiemseebahn",
    "waldeisenbahn",
    "museumsbf",
    "mittelsachsen 527",
    "zvon oberlausitz niederschlesien linie a",
    "zvon oberlausitz niederschlesien linie b",
)


TOKEN_EXPANSIONS = {
    "d": ("dusseldorf",),
    "du": ("duisburg",),
    "do": ("dortmund",),
    "lu": ("ludwigshafen",),
    "ka": ("karlsruhe",),
    "fn": ("friedrichshafen",),
    "sz": ("salzgitter",),
    "pw": ("porta", "westfalica"),
    "fds": ("freudenstadt",),
    "n": ("nuernberg",),
    "me": ("mettmann",),
    "gla": ("gelsenkirchen",),
    "gl": ("gleis",),
    "ob": ("oberer",),
    "unt": ("unterer",),
    "st": ("saint",),
    "nordbf": ("nordbahnhof",),
    "ostbf": ("ostbahnhof",),
    "sudbf": ("sudbahnhof",),
    "stadion": ("erzgebirgsstadion",),
    "westbf": ("westbahnhof",),
}


LIFECYCLE_MARKERS = (
    "abandoned",
    "closed",
    "demolished",
    "destroyed",
    "disused",
    "removed",
    "razed",
)
