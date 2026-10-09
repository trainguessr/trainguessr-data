from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson, publish_nodes  # noqa: E402


def node(station_id: int) -> dict:
    return {
        "type": "node",
        "id": station_id,
        "lat": 45.0,
        "lon": 7.0,
        "tags": {"name": f"Station {station_id}"},
        "category": "test_all",
    }


class NodePublicationTests(unittest.TestCase):
    def test_rejects_empty_and_invalid_output_without_touching_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "nodes.json"
            publish_nodes(target, [node(1)])
            original = target.read_bytes()

            with self.assertRaisesRegex(ValueError, "dataset is empty"):
                publish_nodes(target, [])
            with self.assertRaisesRegex(ValueError, "empty name"):
                publish_nodes(target, [{**node(2), "tags": {"name": ""}}])

            self.assertEqual(original, target.read_bytes())

    def test_rejects_an_implausible_shrink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "nodes.json"
            publish_nodes(target, [node(index) for index in range(10)])

            with self.assertRaisesRegex(ValueError, "refusing to replace 10 nodes with 7"):
                publish_nodes(target, [node(index) for index in range(7)])

            self.assertEqual(10, len(load_ndjson(target)))

    def test_accepts_a_small_reviewable_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "nodes.json"
            publish_nodes(target, [node(index) for index in range(10)])
            publish_nodes(target, [node(index) for index in range(8)])

            self.assertEqual(8, len(load_ndjson(target)))
