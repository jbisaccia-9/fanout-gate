"""Six packets that must be refused - each wrong in exactly one way, each caught by
exactly the rule in its name. Every one is a way a per-recipient fan-out really fails."""
from __future__ import annotations

import datetime as dt
import json
import math
import shutil
from pathlib import Path

from . import fmt, gate, render, workbook
from .pipeline import sources_for, write_packet
from .reconcile import documented_lines
from .resolve import resolve
from .seed import AMBIGUOUS

DESCRIPTIONS = {
    "g1-stale-week": "this week's announcement has arrived; the workbook on the share is still last week's",
    "g2-ambiguous-recipient": "two people in the directory share the lead's name; message addressed to the first hit",
    "g3-foreign-site": "one row from another lead's portfolio rides along in the table",
    "g4-recomputed-action": "action lines regenerated from the documented formula instead of read from the workbook",
    "g5-rounded-number": "an hours-to-add cell 'helpfully' rounded up to a whole hour",
    "g6-retry-duplicate": "send returned a connection error after delivering; the retry would message the lead twice",
}


def build(data_dir: Path, out_dir: Path) -> list[str]:
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    src = sources_for(data_dir, out_dir / "_no-ledger.json")
    wb = workbook.read(Path(src["workbook"]))
    roster = json.loads(Path(src["roster"]).read_text())
    directory = json.loads(Path(src["directory"]).read_text())
    week, month = wb.week_ending, wb.week_ending.strftime("%B")
    by_lead = wb.by_lead()
    good = [l for l in sorted(by_lead) if resolve(l, wb.lead_ids, roster, directory).status == "resolved"]
    addr = lambda l: resolve(l, wb.lead_ids, roster, directory).address

    def packet(name, lead, html, recipient=None, sources=None):
        return write_packet(out_dir / name, lead, recipient or addr(lead), "roster", wb, sources or src, html)

    # g1: a correct packet, and an announcement that has moved on a week.
    lead = good[0]
    p = out_dir / "g1-stale-week"
    p.mkdir(parents=True)
    nxt = week + dt.timedelta(days=7)
    (p / "announcement.json").write_text(json.dumps(
        {"subject": f"Site KPI Analysis - {nxt.month}.{nxt.day:02d}.{nxt:%y}"}, indent=2) + "\n")
    packet(p.name, lead, render.render(lead, by_lead[lead], week),
           sources={**src, "announcement": (p / "announcement.json").as_posix()})

    # g2: resolution said "ambiguous"; someone took candidates[0] anyway.
    res = resolve(AMBIGUOUS, wb.lead_ids, roster, directory)
    packet("g2-ambiguous-recipient", AMBIGUOUS, render.render(AMBIGUOUS, by_lead[AMBIGUOUS], week),
           recipient=res.candidates[0])

    # g3: a join that fanned out. Summary still reflects only the rightful rows.
    lead, other = good[1], good[2]
    packet("g3-foreign-site", lead,
           render.render(lead, by_lead[lead] + by_lead[other][:1], week, summary_rows=by_lead[lead]))

    # g4: pick a lead where recomputing actually diverges, then recompute.
    lead = next(l for l in good if any(documented_lines(s, month) != s.action_lines for s in by_lead[l]))
    packet("g4-recomputed-action", lead,
           render.render(lead, by_lead[lead], week, action_lines=lambda s: documented_lines(s, month)))

    # g5: one cell, rounded up. Nothing else touched.
    lead, site = next((l, s) for l in good for s in by_lead[l] if s.qa_add and s.qa_add != math.ceil(s.qa_add))
    html = render.render(lead, by_lead[lead], week)
    html = html.replace(f">{fmt.hours(site.qa_add)}</td>", f">{math.ceil(site.qa_add)}</td>", 1)
    packet("g5-rounded-number", lead, html)

    # g6: a correct packet whose key is already in the ledger.
    lead = good[3]
    p = out_dir / "g6-retry-duplicate"
    p.mkdir(parents=True)
    (p / "ledger.json").write_text(json.dumps({gate.ledger_key(str(week), wb.sha256, lead): {
        "recipient": addr(lead), "sent_at": f"{week + dt.timedelta(days=2)}T08:00:07"}}, indent=2) + "\n")
    packet(p.name, lead, render.render(lead, by_lead[lead], week),
           sources={**src, "ledger": (p / "ledger.json").as_posix()})
    return sorted(DESCRIPTIONS)
