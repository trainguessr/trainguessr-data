from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))
import denmark


def _feed(path: Path, transfers: str) -> None:
    files = {
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,platform_code\n"
            "000008600101,Alpha (Letbane),55.0,12.0,0,,\n"
            "000008600102,Alpha (Letbane),55.001,12.001,0,,\n"
        ),
        "routes.txt": "route_id,route_short_name,route_type\nL,L,0\n",
        "trips.txt": "route_id,service_id,trip_id,direction_id\nL,S,T1,0\nL,S,T2,1\n",
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,10:00:00,10:00:00,000008600101,1\n"
            "T2,10:05:00,10:05:00,000008600102,1\n"
        ),
        "transfers.txt": (
            "from_stop_id,to_stop_id,transfer_type,min_transfer_time\n" + transfers
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in files.items():
            archive.writestr(name, value)


def test_bidirectional_provider_transfer_family_is_one_node(tmp_path: Path) -> None:
    feed = tmp_path / "feed.zip"
    _feed(
        feed,
        "000008600101,000008600102,2,60\n"
        "000008600102,000008600101,2,60\n",
    )

    nodes = denmark.build_nodes(feed)

    assert [node["id"] for node in nodes] == ["8600101"]
    assert nodes[0]["tags"]["stop_ids"] == ["8600101", "8600102"]
    assert nodes[0]["tags"]["provider_place_ids"] == ["8600101", "8600102"]


def test_name_match_without_complete_provider_transfer_family_stays_distinct(
    tmp_path: Path,
) -> None:
    feed = tmp_path / "feed.zip"
    _feed(feed, "000008600101,000008600102,2,60\n")

    nodes = denmark.build_nodes(feed)

    assert [node["id"] for node in nodes] == ["8600101", "8600102"]
