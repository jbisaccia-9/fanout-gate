"""The gate. It grades a packet on disk - the rendered HTML and its envelope - against the
sources the envelope names. It shares no state with the code that built the packet.

  G1 freshness   the week being sent is the week that was published, from these exact bytes
  G2 recipient   the address is the ONE address this lead resolves to
  G3 isolation   every site of this lead exactly once; no site of anyone else
  G4 verbatim    action lines match the stored text both directions, character for character
  G5 numbers     no number in the message that the workbook did not supply
  G6 once        this (week, file, lead) has not already been sent
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import render, workbook
from .resolve import resolve

RULES = ("G1", "G2", "G3", "G4", "G5", "G6")
RULE_NAMES = {"G1": "freshness", "G2": "recipient", "G3": "isolation",
              "G4": "verbatim", "G5": "numbers", "G6": "once"}
SUBJECT_WEEK = re.compile(r"(\d{1,2})\.(\d{2})\.(\d{2})\s*$")


@dataclass
class Verdict:
    packet: str
    failures: dict[str, list[str]] = field(default_factory=dict)

    def fail(self, rule: str, why: str):
        self.failures.setdefault(rule, []).append(why)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def rules_failed(self) -> list[str]:
        return [r for r in RULES if r in self.failures]

    def to_json(self) -> dict:
        return {"packet": self.packet, "passed": self.passed,
                "rules": {r: {"name": RULE_NAMES[r], "passed": r not in self.failures,
                              "failures": self.failures.get(r, [])} for r in RULES}}

    def line(self) -> str:
        if self.passed:
            return f"PASS     {self.packet}"
        first = self.rules_failed[0]
        more = len(self.failures[first]) - 1
        return (f"REFUSED  {self.packet:<28} {','.join(self.rules_failed)}  "
                f"{self.failures[first][0]}" + (f" (+{more} more)" if more > 0 else ""))


def announced_week(announcement: dict) -> dt.date | None:
    """The publication signal is an email whose subject ends 'M.DD.YY'."""
    m = SUBJECT_WEEK.search(announcement.get("subject", ""))
    return dt.date(2000 + int(m[3]), int(m[1]), int(m[2])) if m else None


def ledger_key(week: str, sha: str, lead: str) -> str:
    return f"{week}|{sha}|{lead}"


def _load(path, default):
    p = Path(path) if path else None
    return json.loads(p.read_text()) if p and p.exists() else default


def freshness(workbook_path, announcement_path) -> tuple[list[str], workbook.Workbook | None]:
    """G1 on the sources alone - the pipeline calls this before it builds anything."""
    why = []
    if not workbook_path or not Path(workbook_path).exists():
        return ["no workbook on the share"], None
    wb = workbook.read(Path(workbook_path))
    ann = announced_week(_load(announcement_path, {}))
    if ann is None:
        why.append("no publication announcement - nothing says this week is final")
    if wb.week_ending is None:
        why.append(f"workbook {workbook.WEEK_CELL} holds no week-ending date")
    if wb.filename_week != wb.week_ending:
        why.append(f"filename says {wb.filename_week}, sheet says {wb.week_ending}")
    if ann and wb.week_ending and ann != wb.week_ending:
        why.append(f"announced week {ann} but workbook on the share is {wb.week_ending} - stale")
    return why, wb


def grade(packet_dir: Path, mode: str = "build") -> Verdict:
    packet_dir = Path(packet_dir)
    v = Verdict(packet_dir.name)
    env = json.loads((packet_dir / "envelope.json").read_text())
    msg = render.parse((packet_dir / "message.html").read_text(encoding="utf-8"))
    src = env["sources"]
    lead = env["lead"]

    # G1 ---------------------------------------------------------------------------------
    why, wb = freshness(src.get("workbook"), src.get("announcement"))
    for w in why:
        v.fail("G1", w)
    if wb is None:
        return v
    if env.get("week_ending") != str(wb.week_ending):
        v.fail("G1", f"packet built for {env.get('week_ending')}, workbook is {wb.week_ending}")
    if env.get("workbook_sha256") != wb.sha256:
        v.fail("G1", "workbook was revised after this packet was built - rebuild from the new bytes")

    # G2 ---------------------------------------------------------------------------------
    res = resolve(lead, wb.lead_ids, _load(src.get("roster"), {}), _load(src.get("directory"), []))
    if res.status != "resolved":
        v.fail("G2", f"{lead}: {res.reason} - skip and report, never guess")
    elif env.get("recipient") != res.address:
        v.fail("G2", f"addressed to {env.get('recipient')} but {lead} resolves to {res.address}")
    if msg.greeting != render.greeting(lead):
        v.fail("G2", f"greeting {msg.greeting!r} is not this lead's")

    # G3 ---------------------------------------------------------------------------------
    mine = {s.site: s for s in wb.sites if s.lead == lead}
    owner = {s.site: s.lead for s in wb.sites}
    seen: dict[str, int] = {}
    for row in msg.rows:
        seen[row.site] = seen.get(row.site, 0) + 1
    for site, n in seen.items():
        if site not in mine:
            v.fail("G3", f"foreign site {site!r} (belongs to {owner.get(site, 'nobody in this workbook')})")
        elif n > 1:
            v.fail("G3", f"{site!r} appears {n} times")
    for site in mine:
        if site not in seen:
            v.fail("G3", f"{site!r} is in this lead's portfolio but not in the message")
    if msg.headers != render.HEADERS:
        v.fail("G3", f"unexpected columns {msg.headers}")

    # G4 + G5, per row that G3 accepted as this lead's -----------------------------------
    for row in msg.rows:
        s = mine.get(row.site)
        if s is None:
            continue
        stored = s.action_lines
        missing = [ln for ln in stored if ln not in row.bullets]
        untraced = [b for b in row.bullets if b not in stored]
        for ln in missing:
            v.fail("G4", f"{row.site}: stored line missing from message: {ln!r}")
        for b in untraced:
            v.fail("G4", f"{row.site}: bullet not in the workbook: {b!r}")
        if not missing and not untraced and row.bullets != stored:
            v.fail("G4", f"{row.site}: lines reordered or repeated")
        want = render.cells(s)
        for head, got, exp in zip(render.HEADERS[1:], row.cells[1:], want[1:]):
            if got != exp:
                v.fail("G5", f"{row.site} / {head}: message says {got!r}, workbook says {exp!r}")
    # The message is a greeting, a table and a summary. Anything else is authored prose, and
    # authored prose is where unsourced numbers live.
    for extra in msg.paragraphs[1:-1] + msg.stray:
        v.fail("G5", f"text the workbook did not supply: {extra[:60]!r}")
    if mine and msg.summary != render.summary(list(mine.values()), wb.week_ending):
        v.fail("G5", "summary line does not equal the totals of this lead's rows")

    # G6 ---------------------------------------------------------------------------------
    if mode == "send":
        ledger = _load(src.get("ledger"), {})
        hit = ledger.get(ledger_key(str(wb.week_ending), wb.sha256, lead))
        if hit:
            v.fail("G6", f"already sent {hit['sent_at']} - check the outbox before retrying")
    return v


def check_dir(root: Path, mode: str = "build") -> list[Verdict]:
    out = []
    for env in sorted(Path(root).glob("*/envelope.json")):
        verdict = grade(env.parent, mode)
        (env.parent / "grading.json").write_text(json.dumps(verdict.to_json(), indent=2) + "\n")
        out.append(verdict)
    return out
