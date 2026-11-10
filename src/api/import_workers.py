"""Copies the worker list CSV (data/workers.csv) into the workers table.

Existing badges are updated, new ones added; workers missing from the CSV are left as they are.

Usage:
    python -m api.import_workers data/workers.csv
"""

import argparse
from pathlib import Path

from sqlalchemy import select

from api.db import Worker, make_sessionmaker
from station.workers import load_workers


def import_workers(csv_path: Path, db_url: str | None = None) -> tuple[int, int]:
    """Returns (added, updated)."""
    added = updated = 0
    with make_sessionmaker(db_url)() as session:
        for w in load_workers(csv_path).values():
            row = session.scalar(select(Worker).where(Worker.badge_no == w.badge_no))
            if row is None:
                row = Worker(badge_no=w.badge_no)
                session.add(row)
                added += 1
            else:
                updated += 1
            row.name, row.department, row.active = w.name, w.department, True
            row.reference_photo_path = str(w.photo) if w.photo else None
        session.commit()
    return added, updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.import_workers", description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="worker list, e.g. data/workers.csv")
    args = parser.parse_args(argv)
    added, updated = import_workers(args.csv)
    print(f"workers: {added} added, {updated} updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
