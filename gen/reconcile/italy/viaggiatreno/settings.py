"""Source locations and reviewed policy constants for Italian providers."""
from __future__ import annotations

import re
from common.io import ROOT


CACHE_DIR = ROOT / "cache" / "italy" / "rfi" / "viaggiatreno"


DEFAULT_NODES = ROOT / "nodes" / "nodes-italy-rfi.json"


DEFAULT_REVIEW = CACHE_DIR / "promotion-review.json"


DEFAULT_PROGRESS = CACHE_DIR / "progress.json"


DEFERRED_SEED = ROOT / "overrides" / "italy-rfi-viaggiatreno-deferred.json"


VT_FIELDS = {
    "viaggiatreno_station_id",
    "viaggiatreno_name",
    "viaggiatreno_region",
    "viaggiatreno_match_distance_m",
    "viaggiatreno_match_method",
    "viaggiatreno_reviewed",
    "viaggiatreno_review_note",
}


VALID_VT_ID = re.compile(r"^S\d{5}$")
