"""Who each card belongs to (the workers table of CLAUDE.md §5) until the database exists.

The list is a CSV with the columns badge_no, name, department, photo; photo is a reference photo
path relative to the CSV. Names and photos are personal data, so the real file stays out of git;
data/workers.example.csv shows the format.
"""

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Worker:
    badge_no: str
    name: str
    department: str = ""
    photo: Path | None = None

    @property
    def initials(self) -> str:
        return "".join(part[0] for part in self.name.split()[:2]).upper()


def load_workers(path: Path) -> dict[str, Worker]:
    """badge_no -> Worker. Accepts comma or semicolon CSV, which Excel writes on Turkish Windows."""
    text = path.read_text(encoding="utf-8-sig")  # -sig: Excel adds a byte-order mark
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;")
    workers = {}
    for row in csv.DictReader(text.splitlines(), dialect=dialect):
        badge = (row.get("badge_no") or "").strip()
        if not badge:
            continue
        photo = (row.get("photo") or "").strip()
        workers[badge] = Worker(
            badge_no=badge,
            name=(row.get("name") or "").strip(),
            department=(row.get("department") or "").strip(),
            photo=path.parent / photo if photo else None,
        )
    return workers
