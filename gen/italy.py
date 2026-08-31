#!/usr/bin/env python3
"""Single public entrypoint for all currently supported Italian data providers."""
from __future__ import annotations

import argparse

from countries.italy import eav, fer, fn, fse, legacy, review, rfi, tt

PROVIDERS = {
    "rfi": rfi.main,
    "fn": fn.main,
    "fse": fse.main,
    "tt": tt.main,
    "fer": fer.main,
    "eav": eav.main,
}
ORDER = ("rfi", "fn", "fse", "tt", "fer", "eav")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate one provider or all providers")
    generate.add_argument("provider", choices=[*ORDER, "all"])

    review_parser = sub.add_parser("review", help="review provider changes")
    review_parser.add_argument("provider", choices=[*ORDER, "all"])

    rebuild = sub.add_parser("rebuild", help="run the conservative legacy rebuild")
    rebuild.add_argument("provider", choices=[*ORDER, "all"])
    rebuild.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "generate":
        providers = ORDER if args.provider == "all" else (args.provider,)
        for provider in providers:
            rc = PROVIDERS[provider]()
            if rc:
                return int(rc)
        return 0

    if args.command == "review":
        return review.main([args.provider])

    legacy_args = [args.provider]
    if args.dry_run:
        legacy_args.append("--dry-run")
    return legacy.main(legacy_args)


if __name__ == "__main__":
    raise SystemExit(main())
