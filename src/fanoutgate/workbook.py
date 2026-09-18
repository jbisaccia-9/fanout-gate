"""Read the weekly ops workbook. Columns are addressed by NUMBER, not letter or name:
the upstream file is a table whose letters shift between revisions."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from openpyxl import load_workbook

SHEET_SITES = "Site View"
SHEET_LEADS = "Lead View"
WEEK_CELL = "C3"            # week-ending date lives in the title block
SITE_HEADER_ROWS = (5, 6)   # two-row header
SITE_FIRST_ROW = 7
LEAD_HEADER_ROW = 3
LEAD_FIRST_ROW = 4

# 1-indexed positions in Site View. The gaps are deliberate: upstream carries columns
# this pipeline has no business reading.
COL = {
    "site_id": 2, "site": 3, "region": 4, "lead": 6,
    "service_wk": 8, "service_mtd": 9,
    "qa_wk": 12, "qa_mtd": 13,
    "qa_pct_wk": 15, "qa_pct_mtd": 16, "qa_add": 17,
    "train_wk": 19, "train_mtd": 20, "train_add": 21, "train_auth_mtd": 23,
    "remote_pct_mtd": 27,
    "action_plan": 29,
}
LEAD_COL = {"employee_id": 2, "employee_name": 3}
NUMERIC = ("service_wk", "service_mtd", "qa_wk", "qa_mtd", "qa_pct_wk", "qa_pct_mtd", "qa_add",
           "train_wk", "train_mtd", "train_add", "train_auth_mtd", "remote_pct_mtd")
ACTION_PREFIX = "(x) "
FILENAME_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\.xlsx$")


@dataclass(frozen=True)
class Site:
    site_id: str
    site: str
    region: str
    lead: str
    service_wk: float | None
    service_mtd: float | None
    qa_wk: float | None
    qa_mtd: float | None
    qa_pct_wk: float | None
    qa_pct_mtd: float | None
    qa_add: float | None
    train_wk: float | None
    train_mtd: float | None
    train_add: float | None
    train_auth_mtd: float | None
    remote_pct_mtd: float | None
    action_plan: str

    @property
    def action_lines(self) -> list[str]:
        """The stored Action Plan, split and de-prefixed. Nothing else is done to it."""
        out = []
        for line in (self.action_plan or "").split("\n"):
            if not line.strip():
                continue
            out.append(line[len(ACTION_PREFIX):] if line.startswith(ACTION_PREFIX) else line)
        return out


@dataclass
class Workbook:
    path: Path
    sha256: str
    week_ending: dt.date | None
    filename_week: dt.date | None
    sites: list[Site] = field(default_factory=list)
    lead_ids: dict[str, str] = field(default_factory=dict)   # "Last First" -> employee id

    def by_lead(self) -> dict[str, list[Site]]:
        out: dict[str, list[Site]] = {}
        for s in self.sites:
            out.setdefault(s.lead, []).append(s)
        return out


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def filename_week(path: Path) -> dt.date | None:
    m = FILENAME_RE.search(Path(path).name)
    return dt.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def find_workbook(data_dir: Path) -> Path | None:
    hits = sorted(Path(data_dir).glob("*.xlsx"))
    return hits[-1] if hits else None


def _num(v):
    return None if v is None or v == "" else float(v)


@lru_cache(maxsize=16)
def _read_cached(path_str: str, sha: str) -> Workbook:
    path = Path(path_str)
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[SHEET_SITES]
    week = ws[WEEK_CELL].value
    if isinstance(week, dt.datetime):
        week = week.date()

    sites = []
    for row in ws.iter_rows(min_row=SITE_FIRST_ROW, values_only=True):
        def get(key, row=row):
            return row[COL[key] - 1] if len(row) >= COL[key] else None
        if not get("site_id"):
            continue
        sites.append(Site(
            site_id=str(get("site_id")), site=str(get("site")), region=str(get("region") or ""),
            lead=str(get("lead")),
            **{k: _num(get(k)) for k in NUMERIC},
            action_plan=str(get("action_plan") or ""),
        ))

    lead_ids = {}
    for row in wb[SHEET_LEADS].iter_rows(min_row=LEAD_FIRST_ROW, values_only=True):
        if len(row) >= LEAD_COL["employee_name"] and row[LEAD_COL["employee_id"] - 1]:
            lead_ids[str(row[LEAD_COL["employee_name"] - 1])] = str(row[LEAD_COL["employee_id"] - 1])
    wb.close()
    return Workbook(path=path, sha256=sha,
                    week_ending=week if isinstance(week, dt.date) else None,
                    filename_week=filename_week(path), sites=sites, lead_ids=lead_ids)


def read(path: Path) -> Workbook:
    """Hash the bytes on disk first; the parse is cached per (path, hash), so a file
    revised after it was announced is never served from a stale read."""
    path = Path(path)
    return _read_cached(str(path), sha256_of(path))
