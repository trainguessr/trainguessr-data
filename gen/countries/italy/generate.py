#!/usr/bin/env python3
"""Single public entrypoint for all currently supported Italian data providers."""
from __future__ import annotations

import argparse
import sys

from common.io import add_cache_flag
from countries.italy import eav, fer, fn, fse, rfi, sta, tt
from countries.italy.reviewed import rebuild as reviewed_rebuild
from countries.italy import review as italy_review

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
    arguments = sys.argv[1:] if argv is None else list(argv)
    if (
        len(arguments) >= 3
        and arguments[0] == "generate"
        and arguments[1] in PROVIDERS
        and "--help" in arguments[2:]
    ):
        previous_program = sys.argv[0]
        sys.argv[0] = f"python3 -m gen.countries italy generate {arguments[1]}"
        try:
            return int(PROVIDERS[arguments[1]](["--help"]) or 0)
        finally:
            sys.argv[0] = previous_program

    parser = argparse.ArgumentParser(description="Generate and review Italian station files.")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate one provider or all providers")
    generate.add_argument("provider", choices=[*GENERATE_ORDER, "all"])
    add_cache_flag(generate)

    generate.add_argument("--audit-only", action="store_true", help="STA only: inspect evidence, do not publish")
    generate.add_argument("--verbose", action="store_true", help="STA only: show per-station StopFinder evidence")
    review_parser = sub.add_parser("review", help="review provider changes")
    review_parser.add_argument("provider", choices=[*REVIEWED_ORDER, "all"])

    rebuild = sub.add_parser("rebuild", help="rebuild from reviewed nodes and provider catalogues")
    rebuild.add_argument("provider", choices=[*REVIEWED_ORDER, "all"])
    rebuild.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "generate":
        providers = GENERATE_ORDER if args.provider == "all" else (args.provider,)
        if (args.audit_only or args.verbose) and args.provider != "sta":
            parser.error("--audit-only and --verbose only apply to the STA provider")
        for provider in providers:
            provider_args = ["--cache"] if args.cache else []
            if provider == "sta":
                if args.audit_only:
                    provider_args.append("--audit-only")
                if args.verbose:
                    provider_args.append("--verbose")
            rc = PROVIDERS[provider](provider_args)
            if rc:
                return int(rc)
        return 0

    if args.command == "review":
        return italy_review.main([args.provider])

    rebuild_args = [args.provider]
    if args.dry_run:
        rebuild_args.append("--dry-run")
    return reviewed_rebuild.main(rebuild_args)


if __name__ == "__main__":
    raise SystemExit(main())
