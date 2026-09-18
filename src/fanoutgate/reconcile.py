"""The Action Plan rules AS DOCUMENTED by the workbook's owner - and a measurement of how
often they reproduce what the workbook actually stores. This module is never in the send
path. It exists to keep the argument for G4 honest and re-runnable."""
from __future__ import annotations

import math

from . import fmt
from .seed import QA_HIGH, QA_TARGET, REMOTE_MAX
from .workbook import Site, Workbook


def documented_lines(s: Site, month: str) -> list[str]:
    lines = []
    if s.qa_pct_mtd is not None and s.qa_pct_mtd > QA_HIGH:
        lines.append("Discuss high QA % of Service MTD with RM")
    if s.qa_pct_mtd is not None and s.qa_pct_mtd < QA_TARGET:
        lines.append(f"Add at least {fmt.hours(s.qa_add)} additional QA hours to {month}")
    # Documented: use the capped 'hours to add' column, rounded UP to a whole hour.
    if (s.train_auth_mtd or 0) > 0 and (s.train_add or 0) > 0:
        lines.append(f"Add {math.ceil(s.train_add)} Tenant training hours to {month}")
    # Documented: 'w/o authorization' sorts BEFORE the remote-QA line.
    if (s.train_auth_mtd or 0) <= 0 and (s.train_mtd or 0) > 0:
        lines.append("Tenant training delivered w/o authorization; consider requesting authorization")
    if s.remote_pct_mtd is not None and s.remote_pct_mtd >= REMOTE_MAX:
        lines.append("Discuss excessive remote QA with RM")
    return lines


def report(wb: Workbook) -> dict:
    month = wb.week_ending.strftime("%B")
    rows = exact = train_rows = train_match = order_only = 0
    for s in wb.sites:
        rows += 1
        stored, doc = s.action_lines, documented_lines(s, month)
        exact += stored == doc
        order_only += stored != doc and sorted(stored) == sorted(doc)
        st = [x for x in stored if "Tenant training hours" in x]
        dc = [x for x in doc if "Tenant training hours" in x]
        if st or dc:
            train_rows += 1
            train_match += st == dc
    return {"rows": rows, "rows_exact": exact, "training_lines": train_rows,
            "training_lines_reproduced": train_match, "order_only_mismatches": order_only}


def render_report(r: dict) -> str:
    pc = lambda a, b: f"{100 * a / b:.0f}%" if b else "n/a"
    return "\n".join([
        f"rows reconciled                       {r['rows']}",
        f"documented formula reproduces row     {r['rows_exact']}/{r['rows']} ({pc(r['rows_exact'], r['rows'])})",
        f"  training lines reproduced           {r['training_lines_reproduced']}/{r['training_lines']} "
        f"({pc(r['training_lines_reproduced'], r['training_lines'])})",
        f"  rows differing only in line order   {r['order_only_mismatches']}",
        f"stored text read verbatim reproduces  {r['rows']}/{r['rows']} (100%) - by construction",
        "",
        "The 'hours to add' column and the action text disagree inside the same workbook.",
        "One of them is wrong and this pipeline does not get to decide which. It reads the text.",
    ])
