#!/usr/bin/env python3
"""Single public entrypoint for all currently supported Italian data providers."""
from __future__ import annotations

import argparse

from countries.italy import eav, fer, fn, fse, reviewed, rfi, sta, tt
from reconcile import italy_review

PROVIDERS = {
    "rfi": rfi.main,
    "fn": fn.main,
    "fse": fse.main,
    "tt": tt.main,
    "fer": fer.main,
    "eav": eav.main,
    "sta": sta.main,
}
REVIEWED_ORDER = ("rfi", "fn", "fse", "tt", "fer", "eav")
GENERATE_ORDER = (*REVIEWED_ORDER, "sta")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate one provider or all providers")
    generate.add_argument("provider", choices=[*GENERATE_ORDER, "all"])
    generate.add_argument(
        "--write-nodes", action="store_true",
        help="STA only: write the exact resolved catalogue to nodes-italy-sta.json",
    )

    review_parser = sub.add_parser("review", help="review provider changes")
    review_parser.add_argument("provider", choices=[*REVIEWED_ORDER, "all"])

    rebuild = sub.add_parser("rebuild", help="rebuild from reviewed nodes and provider catalogues")
    rebuild.add_argument("provider", choices=[*REVIEWED_ORDER, "all"])
    rebuild.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "generate":
        providers = GENERATE_ORDER if args.provider == "all" else (args.provider,)
        if args.write_nodes and args.provider != "sta":
            parser.error("--write-nodes is only valid with 'generate sta'")
        for provider in providers:
            provider_args = ["--write-nodes"] if provider == "sta" and args.write_nodes else []
            rc = PROVIDERS[provider](provider_args) if provider in {"sta", "fse"} else PROVIDERS[provider]()
            if rc:
                return int(rc)
        return 0

    if args.command == "review":
        return italy_review.main([args.provider])

    rebuild_args = [args.provider]
    if args.dry_run:
        rebuild_args.append("--dry-run")
    return reviewed.main(rebuild_args)


if __name__ == "__main__":
    raise SystemExit(main())
