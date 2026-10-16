"""Interactive reviewer for TrainGuessr RFI -> ViaggiaTreno station mappings.

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

Typical use from the repository root::

    PYTHONPATH=gen python3 gen/reconcile/italy_rfi_viaggiatreno.py

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

No provider ID is ever generated arithmetically."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from common.io import ROOT, publish_nodes
from reconcile.italy.viaggiatreno.candidates import candidate_list, decision_from_candidate, fmt, proposed
from reconcile.italy.viaggiatreno.publication import apply_decisions
from reconcile.italy.viaggiatreno.settings import DEFAULT_NODES, DEFAULT_PROGRESS, DEFAULT_REVIEW, VALID_VT_ID
from reconcile.italy.viaggiatreno.state import (
    bootstrap_progress,
    choose_deferred,
    load_jsonl,
    load_progress,
    load_review,
    save_progress,
)


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
        help="Replacement JSONL output (default: update --nodes in place)",
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
            publish_nodes(output, final_rows)
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
        publish_nodes(output, final_rows)
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
    publish_nodes(output, final_rows)
    save_progress(progress_path, progress)

    accepted_ids = {
        pid for pid, d in decisions.items()
        if isinstance(d, dict) and d.get("action") == "accept"
    }
    print(f"\nWrote replacement nodes file: {output}")
    print(f"Total accepted VT mappings written: {len(accepted_ids)}")
    print(f"Progress file: {progress_path}")
    return 0
