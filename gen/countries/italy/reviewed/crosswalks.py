"""Apply exact, reviewed UIC stop mappings to Italian provider nodes."""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Any

from countries.italy.reviewed.settings import STATION_UIC_CROSSWALKS


def load_station_uic_crosswalks(path: Path = STATION_UIC_CROSSWALKS) -> list[dict[str, Any]]:
    """Read reviewed ID pairs and check that each row names one station stop."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "operator", "fn_station_id", "rfi_station_id", "viaggiatreno_station_id",
            "expected_node_name", "expected_viaggiatreno_name", "regione_stop_id",
            "regione_stop_name", "regione_stop_lat_raw", "regione_stop_lon_raw",
            "regione_stop_lat", "regione_stop_lon", "uic_ref", "uic_name",
            "uic_stop_lat", "uic_stop_lon", "uic_location_type", "uic_parent_station",
            "uic_platform_code", "uic_original_stop_id", "uic_didok", "granularity",
            "source_tag", "review_note", "previous_uic_ref", "previous_uic_name",
            "previous_uic_source",
            "oebb_station_id", "hafas_gid", "hafas_crd_x", "hafas_crd_y",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        rows = [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]

    if not rows:
        raise ValueError(f"{path}: add at least one reviewed station mapping")

    seen_provider: set[tuple[str, str]] = set()
    seen_uic: set[str] = set()
    for line, row in enumerate(rows, 2):
        context = f"{path}:{line}"
        operator = row["operator"].strip()
        fn_id = row["fn_station_id"].strip()
        rfi_id = row["rfi_station_id"].strip()
        vt_id = row["viaggiatreno_station_id"].strip()
        uic = row["uic_ref"].strip()
        node_name = row["expected_node_name"].strip()
        if operator == "fn":
            if not fn_id or rfi_id or vt_id:
                raise ValueError(f"{context}: enter only the exact FN station ID")
            if row["regione_stop_id"].strip() != fn_id:
                raise ValueError(f"{context}: FN ID must match the Regione station-stop ID")
            provider_ids = [("fn", fn_id)]
        elif operator == "rfi":
            if fn_id or not rfi_id or not vt_id:
                raise ValueError(f"{context}: enter both the exact RFI and ViaggiaTreno IDs")
            # A merged station keeps the Regione record of the merged stop; its
            # ViaggiaTreno ID is then bound by the Trenitalia ID that Trainline
            # records for exactly that ViaggiaTreno station (Como Camerlata).
            merged = bool(row.get("trainline_id", "").strip()) and row.get("trainline_trenitalia_id", "").strip() == uic
            if row["regione_stop_id"].strip() != vt_id and not merged:
                raise ValueError(f"{context}: ViaggiaTreno ID must match the Regione station-stop ID")
            provider_ids = [("rfi", rfi_id), ("viaggiatreno", vt_id)]
            if not row["expected_viaggiatreno_name"].strip():
                raise ValueError(f"{context}: enter the name shown for this ViaggiaTreno ID")
        else:
            raise ValueError(f"{context}: operator must be fn or rfi")
        if not node_name:
            raise ValueError(f"{context}: enter the current station name")
        for namespace, station_id in provider_ids:
            key = (namespace, station_id)
            if key in seen_provider:
                raise ValueError(f"{context}: this {namespace.upper()} ID is listed twice")
            seen_provider.add(key)

        if not re.fullmatch(r"\d{7}", uic):
            raise ValueError(f"{context}: UIC station-stop ID must have seven digits")
        previous_uic = row["previous_uic_ref"].strip()
        previous_fields = (previous_uic, row["previous_uic_name"].strip(), row["previous_uic_source"].strip())
        if any(previous_fields) and not all(previous_fields):
            raise ValueError(f"{context}: document the previous UIC ID, label and source together")
        if previous_uic and (not re.fullmatch(r"\d{7}", previous_uic) or previous_uic == uic):
            raise ValueError(f"{context}: previous UIC ID must be a distinct seven-digit value")
        if uic in seen_uic:
            raise ValueError(f"{context}: this UIC ID is listed twice")
        seen_uic.add(uic)
        if row["granularity"].strip() != "stop":
            raise ValueError(f"{context}: only a station stop can be mapped")
        if not row["regione_stop_name"].strip():
            raise ValueError(f"{context}: enter the Regione station name")
        hafas_fields = ("oebb_station_id", "hafas_gid", "hafas_crd_x", "hafas_crd_y")
        hafas_evidence = any(row[field].strip() for field in hafas_fields)
        if hafas_evidence:
            if operator != "rfi" or any(not row[field].strip() for field in hafas_fields):
                raise ValueError(f"{context}: enter complete RFI/ÖBB HAFAS stop evidence")
            if row["hafas_gid"] != f"U×{uic}" or not row["oebb_station_id"].isdigit():
                raise ValueError(f"{context}: HAFAS must publish this exact UIC alias for one stop ID")
            if any(row[field].strip() for field in (
                "regione_stop_lat_raw", "regione_stop_lon_raw", "regione_stop_lat", "regione_stop_lon",
            )):
                raise ValueError(f"{context}: keep HAFAS coordinates separate from Regione coordinates")
            try:
                x = int(row["hafas_crd_x"])
                y = int(row["hafas_crd_y"])
                hafas_lat = float(row["uic_stop_lat"])
                hafas_lon = float(row["uic_stop_lon"])
            except ValueError as exc:
                raise ValueError(f"{context}: check the exact HAFAS stop coordinates") from exc
            if (x <= 0 or y <= 0 or abs(hafas_lon - x / 1_000_000) > 0.000001
                    or abs(hafas_lat - y / 1_000_000) > 0.000001):
                raise ValueError(f"{context}: HAFAS crd must normalize to the recorded stop coordinates")
        else:
            for field in ("regione_stop_lat_raw", "regione_stop_lon_raw", "regione_stop_lat", "regione_stop_lon"):
                if not row[field].strip():
                    raise ValueError(f"{context}: enter the Regione coordinate evidence")
        coordinate_fields = [("uic_stop_lat", -90, 90), ("uic_stop_lon", -180, 180)]
        if not hafas_evidence:
            coordinate_fields.extend((
                ("regione_stop_lat", -90, 90), ("regione_stop_lon", -180, 180),
            ))
        for field, low, high in coordinate_fields:
            try:
                coordinate = float(row[field])
            except ValueError as exc:
                raise ValueError(f"{context}: check the station coordinates") from exc
            if not math.isfinite(coordinate) or not low <= coordinate <= high:
                raise ValueError(f"{context}: check the station coordinates")
        if row["uic_original_stop_id"].strip() != uic or row["uic_didok"].strip() != uic:
            raise ValueError(f"{context}: UIC IDs must match the official stop ID")
        if row["uic_location_type"].strip() != "0":
            raise ValueError(f"{context}: only a station-stop record can be mapped")
        if row["uic_parent_station"].strip() != f"Parent{uic}" or row["uic_platform_code"].strip():
            raise ValueError(f"{context}: map the station stop, not its parent or platform")
        for field in ("uic_name", "uic_stop_lat", "uic_stop_lon", "source_tag", "review_note"):
            if not row[field].strip():
                raise ValueError(f"{context}: enter the official UIC details and review note")

        # Keep numeric values numeric for consumers and tests.
        row["uic_location_type"] = 0

    return rows


def apply_station_uic_crosswalks(
    operator: str,
    nodes: list[dict[str, Any]],
    crosswalks: list[dict[str, Any]],
) -> set[str]:
    """Add a UIC stop ID only when both provider IDs and both names still match."""
    if operator not in {"fn", "rfi"}:
        return set()

    applied: set[str] = set()
    for row in crosswalks:
        if row["operator"] != operator:
            continue
        matches = []
        for node in nodes:
            tags = node.get("tags") if isinstance(node, dict) else None
            if not isinstance(tags, dict):
                continue
            if operator == "fn":
                is_match = str(node.get("id", "")).strip() == row["fn_station_id"]
            else:
                is_match = (
                    str(node.get("id", "")).strip() == row["rfi_station_id"]
                    and str(tags.get("viaggiatreno_station_id", "")).strip()
                    == row["viaggiatreno_station_id"]
                )
            if is_match:
                matches.append(node)
        provider_label = row["fn_station_id"] if operator == "fn" else row["rfi_station_id"]
        if len(matches) != 1:
            raise ValueError(
                f"italy/{operator}: check station ID {provider_label}; found {len(matches)} matching records"
            )
        node = matches[0]
        tags = node.setdefault("tags", {})
        if _normalise(str(tags.get("name") or "")) != _normalise(row["expected_node_name"]):
            raise ValueError(f"italy/{operator}: check the name for station ID {provider_label}")
        if operator == "rfi" and _normalise(str(tags.get("viaggiatreno_name") or "")) != _normalise(
            row["expected_viaggiatreno_name"]
        ):
            raise ValueError(
                f"italy/rfi: check the ViaggiaTreno name for station ID {row['viaggiatreno_station_id']}"
            )
        current_uic = str(tags.get("uic_ref") or "").strip()
        previous_uic = row["previous_uic_ref"].strip()
        if previous_uic:
            if current_uic == previous_uic:
                if _normalise(str(tags.get("uic_name") or "")) != _normalise(row["previous_uic_name"]):
                    raise ValueError(f"italy/{operator}: check the prior UIC name for station ID {provider_label}")
            elif current_uic == row["uic_ref"]:
                if (str(tags.get("uic_crosswalk_previous_ref") or "").strip() != previous_uic
                        or str(tags.get("uic_crosswalk_previous_source") or "").strip()
                        != row["previous_uic_source"]):
                    raise ValueError(f"italy/{operator}: prior UIC provenance is missing for station ID {provider_label}")
            else:
                raise ValueError(f"italy/{operator}: check the previous UIC ID for station ID {provider_label}")
            tags["uic_crosswalk_previous_ref"] = previous_uic
            tags["uic_crosswalk_previous_name"] = row["previous_uic_name"]
            tags["uic_crosswalk_previous_source"] = row["previous_uic_source"]
        elif current_uic and current_uic != row["uic_ref"]:
            raise ValueError(f"italy/{operator}: station ID {provider_label} already has a different UIC ID")
        current_granularity = str(tags.get("uic_granularity") or "").strip()
        if current_granularity and current_granularity != row["granularity"]:
            raise ValueError(f"italy/{operator}: check the UIC detail for station ID {provider_label}")
        tags["uic_ref"] = row["uic_ref"]
        tags["uic_name"] = row["uic_name"]
        tags["uic_granularity"] = row["granularity"]
        tags["uic_crosswalk_source"] = row["source_tag"]
        applied.add(provider_label)
    return applied


def _normalise(value: str) -> str:
    return " ".join(value.split()).casefold()
