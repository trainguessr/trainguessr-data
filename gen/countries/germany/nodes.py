"""Reviewed node edits and report loading for Germany."""
from __future__ import annotations

import json
from pathlib import Path
from common.io import publish_nodes
from countries.germany.decisions import load_reconciled_stations


def convert_from_json(
    input_path,
    output_path,
    rename_map,
    board_groups=None,
    reconciled_stations=None,
):
    with open(input_path, 'r', encoding='utf-8') as infile:
        data = json.load(infile)
        if not isinstance(data, list):
            raise ValueError(f"{input_path}: expected a station list")
        nodes = []
        board_groups = board_groups or {}
        reconciled_stations = (
            load_reconciled_stations() if reconciled_stations is None else reconciled_stations
        )
        written_ids = set()
        seen_board_groups = set()
        for station in data:
            try:
                station_id = station.get("id")
                if not station_id:
                    raise ValueError("missing station ID")

                location = station.get("location", {})
                lat = location.get("latitude")
                lon = location.get("longitude")
                if lat in (None, "") or lon in (None, ""):
                    raise ValueError("missing coordinates")

                name = station.get("name", "")
                if not name:
                    raise ValueError("missing station name")

                if name in rename_map:
                    name = rename_map[name]

                ril100 = station.get("ril100", "")
                nr = station.get("nr", "")
                weight = station.get("weight", "")

                operator_name = ""
                if "operator" in station and station["operator"] and "name" in station["operator"]:
                    operator_name = station["operator"]["name"]

                address = {}
                if "address" in station:
                    address = station["address"]

                tags = {
                    "name": name,
                    "ril100": ril100,
                    "station_nr": str(nr),
                    "weight": str(weight),
                    "operator": operator_name,
                    "city": address.get("city", ""),
                    "zipcode": address.get("zipcode", ""),
                    "street": address.get("street", "")
                }
                group = board_groups.get(str(station_id))
                if group:
                    expected_name = group.get("name")
                    if expected_name and expected_name != name:
                        raise ValueError(
                            f"Germany board group {station_id} expected {expected_name!r}, got {name!r}"
                        )
                    tags["provider_place_ids"] = group["provider_ids"]
                    seen_board_groups.add(str(station_id))

                node = {
                    "type": "node",
                    "id": int(station_id),
                    "lat": float(lat),
                    "lon": float(lon),
                    "tags": tags,
                    "category": "germany_all"
                }

                nodes.append(node)
                written_ids.add(str(station_id))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid Germany source station {station!r}: {exc}") from exc

        for station in reconciled_stations:
            station_id = str(station.get("id") or "").strip()
            if not station_id or station_id in written_ids:
                continue
            location = station.get("location", {})
            name = str(station.get("name") or "").strip()
            lat = location.get("latitude")
            lon = location.get("longitude")
            if not name or lat in (None, "") or lon in (None, ""):
                raise ValueError(f"Invalid Germany reconciled station: {station_id}")
            name = rename_map.get(name, name)
            node = {
                "type": "node",
                "id": int(station_id),
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "name": name,
                    "ril100": station.get("ril100", ""),
                    "station_nr": "",
                    "weight": "",
                    "operator": "",
                    "city": "",
                    "zipcode": "",
                    "street": "",
                    "source": station.get("source", "reviewed-germany-akn-supplement"),
                },
                "category": "germany_all",
            }
            nodes.append(node)
            written_ids.add(station_id)
        missing_groups = sorted(set(board_groups) - seen_board_groups)
        if missing_groups:
            raise ValueError(
                "Germany board groups reference stations absent from source: "
                + ", ".join(missing_groups)
            )
        publish_nodes(Path(output_path), nodes)
