"""Command-line entry points for ingestion and PMC inspection.

Usage:
    python -m trainingdash.cli ingest-export <export_dir> [--db PATH] [--force]
    python -m trainingdash.cli pmc [--db PATH] [--rtss-scale 1.0]

`ingest-export` walks a Strava bulk export, parsing every `.fit`/`.fit.gz`,
reducing it to derived metrics, and caching results (write-once / idempotent).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .compute.pmc import current_status
from .ingest.fit import parse_fit
from .pipeline import build_pmc, process_activity
from .store import Store

DEFAULT_DB = "data/cache.sqlite"


def ingest_export(args) -> None:
    store = Store(args.db)
    export_dir = Path(args.export_dir)
    fits = sorted(list(export_dir.rglob("*.fit")) + list(export_dir.rglob("*.fit.gz")))
    if not fits:
        print(f"No .fit files found under {export_dir}")
        return
    processed = skipped = failed = 0
    for path in fits:
        try:
            summary, streams = parse_fit(path)
            result = process_activity(store, summary, streams, force=args.force)
            if result is None:
                skipped += 1
            else:
                processed += 1
                print(f"  ✓ {summary.activity_id} {summary.sport:5s} "
                      f"TSS={result.tss if result.sport=='Ride' else result.rtss:.0f}")
        except Exception as exc:  # keep going; one bad file shouldn't halt a backfill
            failed += 1
            print(f"  ✗ {path.name}: {exc}")
    print(f"\nDone. processed={processed} skipped={skipped} failed={failed}")
    store.close()


def pmc(args) -> None:
    store = Store(args.db)
    chart = build_pmc(store, rtss_scale=args.rtss_scale)
    if len(chart.ctl) == 0:
        print("No derived metrics yet — run ingest-export first.")
        return
    status = current_status(chart)
    print("Performance Management Chart (latest):")
    for k, v in status.items():
        print(f"  {k:14s}: {v}")
    store.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="trainingdash")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest-export", help="ingest a Strava bulk export directory")
    p_ing.add_argument("export_dir")
    p_ing.add_argument("--db", default=DEFAULT_DB)
    p_ing.add_argument("--force", action="store_true", help="re-reduce already-cached activities")
    p_ing.set_defaults(func=ingest_export)

    p_pmc = sub.add_parser("pmc", help="print the latest PMC status")
    p_pmc.add_argument("--db", default=DEFAULT_DB)
    p_pmc.add_argument("--rtss-scale", type=float, default=1.0)
    p_pmc.set_defaults(func=pmc)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
