"""Source locations and reviewed policy constants for Germany."""
from __future__ import annotations

import os
from common.io import ROOT


GERMANY_CACHE = os.path.join(ROOT, "cache", "germany")


NPM_REGISTRY_URL = "https://registry.npmjs.org/db-stations/latest"


BOARD_GROUPS_PATH = os.path.join(ROOT, "overrides", "germany-board-groups.json")


RECONCILIATION_PATH = os.path.join(ROOT, "docs", "review", "germany-reconciliation.json")
