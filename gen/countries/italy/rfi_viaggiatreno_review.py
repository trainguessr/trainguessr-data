#!/usr/bin/env python3
"""
Interactive reviewer for TrainGuessr RFI -> ViaggiaTreno station mappings.

Repository-integrated reviewer for RFI -> ViaggiaTreno station mappings.

State is stored under cache/italy/rfi/viaggiatreno/. On first run, accepted
mappings are bootstrapped from the committed RFI nodes and known temporary
deferrals are seeded from overrides/italy-rfi-viaggiatreno-deferred.json.

The optional promotion-review file adds candidate suggestions, but it is not
required: newly added RFI stations can always be reviewed manually with `e`.

When a review pass completes, accepted mappings are written directly to
nodes/nodes-italy-rfi.json. Deferred/rejected stations remain without VT tags.
Every decision is saved immediately, so quitting is safe.

Use --snapshot to immediately write an intermediate nodes JSONL from the decisions
already saved in the progress file, without entering the interactive reviewer.
The progress file is not changed by snapshot mode.

Typical use
-----------
python3 rfi-vt-interactive-review.py \
  trainguessr-data/nodes/nodes-italy-rfi.json \
  rfi-vt-promotion-review.json

Then, after reviewing:
  cp nodes-italy-rfi.reviewed.json \
     trainguessr-data/nodes/nodes-italy-rfi.json

Review commands
---------------
Enter / y       Accept the proposed mapping
n               Reject mapping for this RFI node
e               Enter/edit a VT S-code manually
c               Choose one of the shown candidates
s               Defer for this pass (shown again on the next pass)
b               Go back one reviewed item
q               Save and quit
i               Show raw review record
?               Show help

Accepted/rejected stations already present in the progress file are skipped by default.
A station deferred with `s` is hidden only for the current review pass and is
automatically shown again after starting the next pass with --new-pass.
Use --include-decided only if you explicitly want to revisit accepted/rejected stations.

Default review order is easy-first:
  1. safe proposals (normally pre-accepted and skipped with --accept-safe)
  2. exact-name manual reviews, shortest coordinate discrepancy first
  3. fuzzy-name manual reviews, highest name score first
  4. ambiguous unresolved records
  5. no-result/unmapped records
Use --review-order risk for hardest-first, or --review-order source for the
original node-file order.

For already-safe items shown interactively, pressing Enter accepts the proposal.
For manual-review items, pressing Enter also accepts the proposal after you
visually review it.
For unresolved/ambiguous items, Enter does NOT guess; use c/e/n/s.

No provider ID is ever generated arithmetically.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any

# Allow direct execution from a normal repository checkout.
GEN_ROOT = Path(__file__).resolve().parents[2]
if str(GEN_ROOT) not in sys.path:
    sys.path.insert(0, str(GEN_ROOT))

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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}")
            if not isinstance(row, dict):
                raise SystemExit(f"{path}:{lineno}: expected JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, path)


def load_review(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Review file must contain a JSON object")

    by_id: dict[str, dict[str, Any]] = {}
    for bucket in ("safe_to_promote", "manual_review", "unresolved"):
        rows = data.get(bucket) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("rfi_place_id") or "").strip()
            if not pid:
                continue
            item = dict(row)
            item["_bucket"] = bucket
            by_id[pid] = item
    return by_id


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 2, "review_pass": 1, "decisions": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid progress file: {path}")
    # Schema 2 adds pass-aware temporary deferrals. Old progress files remain valid.
    data["schema_version"] = max(int(data.get("schema_version") or 1), 2)
    data.setdefault("review_pass", 1)
    data.setdefault("decisions", {})
    return data


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)



def bootstrap_progress(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build durable review state from committed runtime mappings + defer seeds."""
    progress: dict[str, Any] = {
        "schema_version": 2,
        "review_pass": 1,
        "decisions": {},
    }
    decisions = progress["decisions"]
    for node in nodes:
        pid = str(node.get("id") or "")
        tags = node.get("tags") if isinstance(node.get("tags"), dict) else {}
        sid = str(tags.get("viaggiatreno_station_id") or "").strip()
        if VALID_VT_ID.fullmatch(sid):
            decisions[pid] = {
                "action": "accept",
                "vt_station_id": sid,
                "vt_name": str(tags.get("viaggiatreno_name") or "").strip() or None,
                "region": tags.get("viaggiatreno_region"),
                "method": "bootstrap_from_committed_nodes",
                "note": "existing reviewed runtime mapping",
            }

    if DEFERRED_SEED.is_file():
        seed = json.loads(DEFERRED_SEED.read_text(encoding="utf-8"))
        for row in seed.get("stations", []):
            pid = str(row.get("rfi_place_id") or "")
            if not pid or pid in decisions:
                continue
            decisions[pid] = {
                "action": "defer",
                "deferred_pass": 1,
                "note": str(row.get("reason") or "deferred_for_now"),
                "source_bucket": "tracked_deferred_seed",
            }
    return progress


def choose_deferred(
    nodes: list[dict[str, Any]],
    decisions: dict[str, Any],
) -> set[str]:
    """Interactively choose which previous deferrals should be retried now."""
    by_id = {str(n.get("id") or ""): n for n in nodes}
    rows = [
        (pid, d) for pid, d in decisions.items()
        if isinstance(d, dict) and d.get("action") == "defer" and pid in by_id
    ]
    if not rows or not sys.stdin.isatty():
        return set()

    rows.sort(key=lambda item: (by_id[item[0]].get("tags", {}).get("name", ""), item[0]))
    print(f"\n{len(rows)} station(s) were deferred in an earlier review.")
    answer = input("Recheck deferred stations now? [n]one / [a]ll / [l]ist-select > ").strip().lower()
    if answer in ("a", "all"):
        return {pid for pid, _ in rows}
    if answer not in ("l", "list"):
        return set()

    print()
    for idx, (pid, decision) in enumerate(rows, 1):
        name = by_id[pid].get("tags", {}).get("name", "")
        print(f"{idx:>3}. {name} ({pid})")
        print(f"     Last time: {decision.get('note') or 'no reason recorded'}")
    raw = input("Numbers to recheck (comma-separated; ranges like 2-5; blank=none): ").strip()
    chosen: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            try:
                a, b = int(left), int(right)
            except ValueError:
                continue
            chosen.update(range(min(a, b), max(a, b) + 1))
        else:
            try:
                chosen.add(int(part))
            except ValueError:
                continue
    return {pid for idx, (pid, _) in enumerate(rows, 1) if idx in chosen}

def fmt(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def candidate_list(record: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = record.get("candidates")
    if isinstance(candidates, list):
        return [c for c in candidates if isinstance(c, dict)]

    nearby = record.get("nearby")
    if isinstance(nearby, list):
        return [c for c in nearby if isinstance(c, dict)]

    if record.get("vt_station_id"):
        return [{
            "id": record.get("vt_station_id"),
            "name": record.get("vt_name"),
            "distance_m": record.get("distance_m"),
            "name_score": record.get("name_score"),
        }]
    return []


def proposed(record: dict[str, Any]) -> tuple[str | None, str | None]:
    sid = record.get("vt_station_id")
    name = record.get("vt_name")
    sid = str(sid).strip() if sid else None
    name = str(name).strip() if name else None
    return sid, name


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
    out = []
    for original in nodes:
        node = json.loads(json.dumps(original))
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
        out.append(node)
    return out


def print_header(
    index: int,
    total: int,
    node: dict[str, Any],
    record: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> None:
    tags = node.get("tags") if isinstance(node.get("tags"), dict) else {}
    print("\n" + "=" * 78)
    print(f"[{index + 1}/{total}] RFI placeId {node.get('id')}")
    print(f"RFI name:      {fmt(tags.get('name'))}")
    print(f"Coordinates:   {fmt(node.get('lat'))}, {fmt(node.get('lon'))}")
    print(f"Category:      {fmt(node.get('category'))}")

    if record:
        bucket = record.get("_bucket")
        print(f"Review bucket: {bucket}")
        sid, name = proposed(record)
        if sid:
            print(f"Proposal:      {sid}  {fmt(name)}")
            print(
                f"Evidence:      distance={fmt(record.get('distance_m'))} m  "
                f"name_score={fmt(record.get('name_score'))}  "
                f"method={fmt(record.get('method'))}"
            )
        else:
            print("Proposal:      none")
            if record.get("status"):
                print(f"Reason/status: {record.get('status')}")
    else:
        print("Review bucket: no review record")
        print("Proposal:      none")

    candidates = candidate_list(record or {})
    if candidates:
        print("Candidates:")
        for n, c in enumerate(candidates, 1):
            print(
                f"  {n:>2}. {fmt(c.get('id')):<8} {fmt(c.get('name')):<36} "
                f"dist={fmt(c.get('distance_m')):>8} m  "
                f"score={fmt(c.get('name_score'))}"
            )

    if decision:
        action = decision.get("action")
        if action == "accept":
            print(
                f"Saved decision: ACCEPT {decision.get('vt_station_id')} "
                f"{decision.get('vt_name') or ''}"
            )
        elif action == "defer":
            print(
                f"Previous pass:   DEFERRED in pass {decision.get('deferred_pass')} — "
                f"{decision.get('note') or 'no reason recorded'}"
            )
        else:
            print(f"Saved decision: {str(action).upper()}")
    print("=" * 78)


def decision_from_candidate(
    record: dict[str, Any],
    sid: str,
    name: str | None,
    *,
    method_override: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    selected = None
    for c in candidate_list(record):
        if str(c.get("id") or "").strip() == sid:
            selected = c
            break

    return {
        "action": "accept",
        "vt_station_id": sid,
        "vt_name": name or (selected or {}).get("name") or record.get("vt_name"),
        "region": (selected or {}).get("region") or record.get("region"),
        "distance_m": (selected or {}).get("distance_m", record.get("distance_m")),
        "name_score": (selected or {}).get("name_score", record.get("name_score")),
        "method": method_override or record.get("method") or "interactive_review",
        "note": note or "accepted_interactively",
        "source_bucket": record.get("_bucket"),
    }


def help_text() -> None:
    print("""
Commands:
  Enter / y   accept proposed mapping
  n           reject / keep this RFI node without a VT mapping
  e           manually enter a VT S-code and optional name
  c           choose candidate number
  s           defer for this pass; show again on the next pass
  b           go back one item
  q           save and quit
  i           print raw review record
  ?           show this help
""")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--nodes",
        type=Path,
        default=DEFAULT_NODES,
        help=f"RFI nodes JSONL (default: {DEFAULT_NODES.relative_to(ROOT)})",
    )
    ap.add_argument(
        "--review",
        type=Path,
        default=DEFAULT_REVIEW,
        help=(
            "Optional promotion-review JSON with candidate suggestions "
            f"(default: {DEFAULT_REVIEW.relative_to(ROOT)})"
        ),
    )
    ap.add_argument(
        "--output",
        type=Path,
        help="Replacement JSONL output (default: nodes-italy-rfi.reviewed.json beside input)",
    )
    ap.add_argument(
        "--progress",
        type=Path,
        help="Resume/progress JSON (default: <output>.progress.json)",
    )
    ap.add_argument(
        "--only",
        choices=("all", "safe", "manual", "unresolved"),
        default="all",
        help="Review only one bucket; default reviews every RFI node",
    )
    ap.add_argument(
        "--start-id",
        help="Jump to a particular RFI placeId",
    )
    ap.add_argument(
        "--accept-safe",
        action="store_true",
        help="Pre-accept safe_to_promote rows, then interactively review the rest",
    )
    ap.add_argument(
        "--write-anyway",
        action="store_true",
        help="Allow final output even when some selected rows are still skipped/unreviewed",
    )
    ap.add_argument(
        "--snapshot",
        action="store_true",
        help=(
            "Immediately write --output from the decisions already saved in --progress "
            "and exit without opening the interactive reviewer. Undecided/rejected RFI "
            "nodes are written without ViaggiaTreno mapping tags."
        ),
    )
    ap.add_argument(
        "--include-decided",
        action="store_true",
        help="Also show stations already accepted/rejected in the progress file",
    )
    ap.add_argument(
        "--new-pass",
        action="store_true",
        help=(
            "Start the next review pass. Stations deferred with `s` in an earlier "
            "pass become eligible again and display their previous defer reason."
        ),
    )
    ap.add_argument(
        "--review-order",
        choices=("easy", "risk", "source"),
        default="easy",
        help="easy = strongest/easiest proposals first; risk = unresolved/ambiguous first; source = original node order",
    )
    args = ap.parse_args()

    if not args.nodes.is_file():
        raise SystemExit(f"Nodes file not found: {args.nodes}")

    output = args.output or args.nodes
    progress_path = args.progress or DEFAULT_PROGRESS

    nodes = load_jsonl(args.nodes)
    by_id = load_review(args.review)
    if progress_path.exists():
        progress = load_progress(progress_path)
    else:
        progress = bootstrap_progress(nodes)
        save_progress(progress_path, progress)
        print(f"Bootstrapped review state: {progress_path.relative_to(ROOT)}")
    decisions: dict[str, Any] = progress["decisions"]
    if args.new_pass:
        progress["review_pass"] = int(progress.get("review_pass") or 1) + 1
        save_progress(progress_path, progress)
    review_pass = int(progress.get("review_pass") or 1)

    rfi_nodes = [n for n in nodes if n.get("category") == "italy_rfi"]
    if not rfi_nodes:
        raise SystemExit("No category=italy_rfi nodes found")

    revisit_deferred = choose_deferred(rfi_nodes, decisions)

    if args.accept_safe:
        for node in rfi_nodes:
            pid = str(node.get("id") or "")
            record = by_id.get(pid)
            if not record or record.get("_bucket") != "safe_to_promote":
                continue
            if pid in decisions:
                continue
            sid, name = proposed(record)
            if sid and VALID_VT_ID.fullmatch(sid):
                decisions[pid] = decision_from_candidate(
                    record, sid, name, note="preaccepted_safe_bucket"
                )
        save_progress(progress_path, progress)

    def included(node: dict[str, Any]) -> bool:
        if args.only == "all":
            return True
        record = by_id.get(str(node.get("id") or ""))
        if not record:
            return args.only == "unresolved"
        mapping = {
            "safe": "safe_to_promote",
            "manual": "manual_review",
            "unresolved": "unresolved",
        }
        return record.get("_bucket") == mapping[args.only]

    def eligible_for_pass(node: dict[str, Any]) -> bool:
        pid = str(node.get("id") or "")
        decision = decisions.get(pid)
        if args.include_decided:
            return True
        if not isinstance(decision, dict):
            return True
        action = decision.get("action")
        if action in ("accept", "reject"):
            return False
        if action == "defer":
            return pid in revisit_deferred or int(decision.get("deferred_pass") or 1) < review_pass
        return True

    queue = [
        n for n in rfi_nodes
        if included(n) and eligible_for_pass(n)
    ]

    original_order = {
        str(n.get("id") or ""): i for i, n in enumerate(rfi_nodes)
    }

    if args.review_order == "risk":
        bucket_rank = {
            "unresolved": 0,
            "manual_review": 1,
            "safe_to_promote": 2,
        }
        queue.sort(
            key=lambda n: (
                bucket_rank.get(
                    (by_id.get(str(n.get("id") or "")) or {}).get("_bucket"),
                    3,
                ),
                original_order.get(str(n.get("id") or ""), 10**9),
            )
        )

    elif args.review_order == "easy":
        def easy_key(node: dict[str, Any]) -> tuple:
            pid = str(node.get("id") or "")
            record = by_id.get(pid) or {}
            bucket = record.get("_bucket")
            method = str(record.get("method") or "")
            status = str(record.get("status") or "")
            try:
                distance = float(record.get("distance_m"))
            except (TypeError, ValueError):
                distance = float("inf")
            try:
                score = float(record.get("name_score"))
            except (TypeError, ValueError):
                score = -1.0

            # Easiest -> hardest:
            #   0 safe proposals (normally already hidden by --accept-safe)
            #   1 manual exact-name matches, shortest first
            #   2 manual fuzzy-name matches, strongest score then shortest
            #   3 ambiguous unresolved
            #   4 no-result/unmapped unresolved
            #   5 anything not represented in the review file
            if bucket == "safe_to_promote":
                tier = 0
                secondary = (distance, -score)
            elif bucket == "manual_review" and method == "exact_normalized_name+coordinates":
                tier = 1
                secondary = (distance, -score)
            elif bucket == "manual_review":
                tier = 2
                secondary = (-score, distance)
            elif bucket == "unresolved" and status == "ambiguous":
                tier = 3
                secondary = (distance, -score)
            elif bucket == "unresolved":
                tier = 4
                secondary = (distance, -score)
            else:
                tier = 5
                secondary = (distance, -score)

            return (
                tier,
                secondary[0],
                secondary[1],
                original_order.get(pid, 10**9),
            )

        queue.sort(key=easy_key)
    if not queue:
        selected_total = sum(1 for n in rfi_nodes if included(n))
        decided_total = sum(
            1 for n in rfi_nodes
            if included(n) and str(n.get("id") or "") in decisions
        )
        if selected_total and decided_total == selected_total:
            print("All stations in the selected queue already have decisions.")
            print(f"Selected: {selected_total}  Decided: {decided_total}")
            print("Use --include-decided to revisit accepted/rejected stations.")
            print("If stations were deferred in this pass, use --new-pass to present them again.")
            final_rows = apply_decisions(nodes, decisions)
            write_jsonl(output, final_rows)
            save_progress(progress_path, progress)
            print(f"Wrote replacement nodes file: {output}")
            return 0
        raise SystemExit("No stations selected by --only")

    total_decisions = len(decisions)
    accepted_total = sum(
        1 for d in decisions.values()
        if isinstance(d, dict) and d.get("action") == "accept"
    )
    rejected_total = sum(
        1 for d in decisions.values()
        if isinstance(d, dict) and d.get("action") == "reject"
    )
    deferred_total = sum(
        1 for d in decisions.values()
        if isinstance(d, dict) and d.get("action") == "defer"
    )
    print(
        f"Loaded {len(rfi_nodes)} RFI nodes. Review pass: {review_pass}. "
        f"Saved decisions: {total_decisions} "
        f"({accepted_total} accepted, {rejected_total} rejected, "
        f"{deferred_total} deferred)."
    )
    print(f"Stations still queued for this run: {len(queue)}")

    if args.snapshot:
        final_rows = apply_decisions(nodes, decisions)
        write_jsonl(output, final_rows)
        undecided_total = sum(
            1 for node in rfi_nodes
            if str(node.get("id") or "") not in decisions
        )
        print(f"\nWrote intermediate snapshot: {output}")
        print(f"Accepted VT mappings written: {accepted_total}")
        print(f"Rejected mappings kept unmapped: {rejected_total}")
        print(f"Deferred mappings kept unmapped: {deferred_total}")
        print(f"Undecided RFI nodes kept unmapped: {undecided_total}")
        print(f"Progress file left unchanged: {progress_path}")
        return 0

    index = 0
    if args.start_id:
        for i, node in enumerate(queue):
            if str(node.get("id") or "") == str(args.start_id):
                index = i
                break
        else:
            raise SystemExit(f"--start-id {args.start_id!r} is not in selected queue")

    history: list[int] = []

    while index < len(queue):
        node = queue[index]
        pid = str(node.get("id") or "")
        record = by_id.get(pid)
        decision = decisions.get(pid)
        print_header(index, len(queue), node, record, decision)

        # Existing decisions still appear so every row can be re-reviewed.
        try:
            raw = input("[Enter/y] accept  [n] reject  [e] edit  [c] candidate  "
                        "[s] defer  [b] back  [q] save+quit  [?] help > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            save_progress(progress_path, progress)
            print(f"Saved progress to {progress_path}")
            print("Resume by running the same command again.")
            return 130

        if raw in ("?", "h", "help"):
            help_text()
            continue
        if raw == "i":
            print(json.dumps(record, ensure_ascii=False, indent=2))
            continue
        if raw == "q":
            save_progress(progress_path, progress)
            print(f"\nSaved progress to {progress_path}")
            print("Resume by running the same command again.")
            print("The final replacement nodes file is written when the review queue is complete.")
            return 0
        if raw == "b":
            if history:
                index = history.pop()
            elif index > 0:
                index -= 1
            continue
        if raw == "s":
            previous = decisions.get(pid)
            previous_note = (
                previous.get("note")
                if isinstance(previous, dict) and previous.get("action") == "defer"
                else None
            )
            prompt = "Why is this impossible/unresolvable for now?"
            if previous_note:
                prompt += f" [previous: {previous_note}]"
            note = input(prompt + " ").strip() or previous_note or "deferred_for_now"
            decisions[pid] = {
                "action": "defer",
                "deferred_pass": review_pass,
                "note": note,
                "source_bucket": (record or {}).get("_bucket"),
            }
            save_progress(progress_path, progress)
            history.append(index)
            index += 1
            continue

        if raw in ("", "y", "yes", "a", "accept"):
            if not record:
                print("No proposal exists. Use e, n, or s.")
                continue
            sid, name = proposed(record)
            if not sid:
                print("No single proposal exists. Use c/e/n/s; refusing to guess.")
                continue
            if not VALID_VT_ID.fullmatch(sid):
                print(f"Invalid proposal ID {sid!r}; refusing to accept.")
                continue
            decisions[pid] = decision_from_candidate(record, sid, name)
            save_progress(progress_path, progress)
            history.append(index)
            index += 1
            continue

        if raw in ("n", "no", "reject", "r"):
            note = input("Optional rejection note: ").strip()
            decisions[pid] = {
                "action": "reject",
                "note": note or "rejected_interactively",
                "source_bucket": (record or {}).get("_bucket"),
            }
            save_progress(progress_path, progress)
            history.append(index)
            index += 1
            continue

        if raw in ("c", "candidate"):
            candidates = candidate_list(record or {})
            if not candidates:
                print("No candidates are present. Use e to enter an exact VT ID manually.")
                continue
            choice = input(f"Candidate number 1-{len(candidates)}: ").strip()
            try:
                selected = candidates[int(choice) - 1]
            except (ValueError, IndexError):
                print("Invalid candidate number.")
                continue
            sid = str(selected.get("id") or "").strip()
            if not VALID_VT_ID.fullmatch(sid):
                print(f"Candidate has invalid VT ID: {sid!r}")
                continue
            name = str(selected.get("name") or "").strip() or None
            decisions[pid] = decision_from_candidate(
                record or {},
                sid,
                name,
                method_override="interactive_candidate_selection",
                note="candidate_selected_interactively",
            )
            save_progress(progress_path, progress)
            history.append(index)
            index += 1
            continue

        if raw in ("e", "edit"):
            sid = input("Exact ViaggiaTreno S-code (S12345): ").strip().upper()
            if not VALID_VT_ID.fullmatch(sid):
                print("Invalid VT S-code. Expected S followed by exactly five digits.")
                continue
            name = input("VT station name (optional): ").strip() or None
            note = input("Evidence/note (recommended): ").strip() or "manual_exact_id"
            decisions[pid] = decision_from_candidate(
                record or {},
                sid,
                name,
                method_override="manual_exact_id",
                note=note,
            )
            save_progress(progress_path, progress)
            history.append(index)
            index += 1
            continue

        print("Unknown command. Type ? for help.")

    selected_ids = {str(n.get("id") or "") for n in queue}
    undecided = sorted(
        pid for pid in selected_ids
        if not isinstance(decisions.get(pid), dict)
        or decisions.get(pid, {}).get("action") not in ("accept", "reject", "defer")
    )

    print("\nReview queue complete.")
    print(f"Accepted: {sum(1 for p in selected_ids if decisions.get(p, {}).get('action') == 'accept')}")
    print(f"Rejected: {sum(1 for p in selected_ids if decisions.get(p, {}).get('action') == 'reject')}")
    print(f"Deferred this pass: {sum(1 for p in selected_ids if decisions.get(p, {}).get('action') == 'defer')}")
    print(f"Still undecided: {len(undecided)}")

    if undecided and not args.write_anyway:
        print("\nSome selected stations are still undecided.")
        print("Re-run to resume, or use --write-anyway if you intentionally want them unmapped.")
        save_progress(progress_path, progress)
        return 2

    final_rows = apply_decisions(nodes, decisions)
    write_jsonl(output, final_rows)
    save_progress(progress_path, progress)

    accepted_ids = {
        pid for pid, d in decisions.items()
        if isinstance(d, dict) and d.get("action") == "accept"
    }
    print(f"\nWrote replacement nodes file: {output}")
    print(f"Total accepted VT mappings written: {len(accepted_ids)}")
    print(f"Progress file: {progress_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
