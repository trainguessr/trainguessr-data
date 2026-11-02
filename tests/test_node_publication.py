from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson, publish_nodes, preserve_outputs_on_failure  # noqa: E402
from common.validate import validate_nodes  # noqa: E402


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
    def test_rejects_null_or_boolean_ids_empty_categories_and_boolean_coordinates(self) -> None:
        for invalid_id in (None, True, False, "  "):
            with self.subTest(id=invalid_id):
                errors = validate_nodes([{**node(1), "id": invalid_id}])
                self.assertTrue(any("ID" in error for error in errors))
        for invalid_category in (None, "", "   "):
            with self.subTest(category=invalid_category):
                errors = validate_nodes([{**node(1), "category": invalid_category}])
                self.assertTrue(any("category must be non-empty text" in error for error in errors))
        for field in ("lat", "lon"):
            errors = validate_nodes([{**node(1), field: True}])
            self.assertIn(f"row 1: invalid {field}", errors)
        self.assertIn("row 1: empty name", validate_nodes([{**node(1), "tags": {"name": None}}]))
        self.assertEqual([], validate_nodes([node(1), {**node(2), "id": "S2"}]))

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


def test_idempotent_node_publication_preserves_mtime(tmp_path, capsys):
    path = tmp_path / "nodes.json"
    publish_nodes(path, [node(1), node(2)])
    stamp = path.stat().st_mtime_ns
    publish_nodes(path, [node(1), node(2)])
    assert path.stat().st_mtime_ns == stamp
    assert "unchanged" in capsys.readouterr().out


def test_failed_index_build_restores_both_files(tmp_path):
    first = tmp_path / "stations.json"
    second = tmp_path / "index.sqlite"
    first.write_bytes(b"original stations")
    second.write_bytes(b"original index")
    with __import__('pytest').raises(RuntimeError, match='index failed'):
        with preserve_outputs_on_failure(first, second):
            first.write_bytes(b"new stations")
            second.write_bytes(b"partial index")
            raise RuntimeError("index failed")
    assert first.read_bytes() == b"original stations"
    assert second.read_bytes() == b"original index"


def test_failed_first_build_removes_partial_outputs(tmp_path):
    a, b = tmp_path / "nodes", tmp_path / "index"
    with __import__('pytest').raises(ValueError):
        with preserve_outputs_on_failure(a, b):
            a.write_bytes(b"partial")
            raise ValueError("oops")
    assert not a.exists() and not b.exists()


def test_publication_ignores_upstream_row_and_key_order(tmp_path):
    path = tmp_path / 'nodes.json'
    publish_nodes(path, [node(2), node(1)])
    original, stamp = path.read_bytes(), path.stat().st_mtime_ns
    reversed_keys = {key: value for key, value in reversed(list(node(1).items()))}
    publish_nodes(path, [node(2), reversed_keys])
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == stamp
    changed = node(2)
    changed['tags']['name'] = 'Updated'
    publish_nodes(path, [node(3), changed, node(1)])
    assert [row['id'] for row in load_ndjson(path)] == [1, 2, 3]
    assert load_ndjson(path)[1]['tags']['name'] == 'Updated'
