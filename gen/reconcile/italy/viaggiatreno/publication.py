"""Guarded publication and candidate construction for Italian providers."""
from __future__ import annotations

import json
from typing import Any
from reconcile.italy.viaggiatreno.settings import VALID_VT_ID, VT_FIELDS


def clear_vt_tags(node: dict[str, Any]) -> dict[str, Any]:
    tags = node.setdefault("tags", {})
    if not isinstance(tags, dict):
        tags = {}
        node["tags"] = tags
    for key in VT_FIELDS:
        tags.pop(key, None)
    return tags


def apply_decisions(
    nodes: list[dict[str, Any]],
    decisions: dict[str, Any],
) -> list[dict[str, Any]]:
    # One JSON round trip retains the original JSON normalization and deep
    # isolation while avoiding two serializer calls per station.
    out = json.loads(json.dumps(nodes))
    for node in out:
        pid = str(node.get("id") or "")
        tags = clear_vt_tags(node)
        decision = decisions.get(pid)

        if isinstance(decision, dict) and decision.get("action") == "accept":
            sid = str(decision.get("vt_station_id") or "").strip()
            if not VALID_VT_ID.fullmatch(sid):
                raise SystemExit(f"Invalid accepted VT ID for RFI {pid}: {sid!r}")
            tags["viaggiatreno_station_id"] = sid

            name = str(decision.get("vt_name") or "").strip()
            if name:
                tags["viaggiatreno_name"] = name

            region = decision.get("region")
            if region not in (None, ""):
                tags["viaggiatreno_region"] = region

            # Review/evidence metadata belongs in the progress/review files,
            # not in the runtime nodes dataset. Keep the nodes diff minimal.

        # Reject means deliberately no VT tags.
    return out
