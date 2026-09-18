"""prepare -> send. Every stage is left on disk under out/<run>/<lead>/."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

from . import gate, render, workbook
from .resolve import resolve


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def sources_for(data_dir: Path, ledger: Path) -> dict:
    data_dir = Path(data_dir)
    wb = workbook.find_workbook(data_dir)
    return {"workbook": wb.as_posix() if wb else None,
            "announcement": (data_dir / "announcement.json").as_posix(),
            "roster": (data_dir / "roster.json").as_posix(),
            "directory": (data_dir / "directory.json").as_posix(),
            "ledger": Path(ledger).as_posix()}


def write_packet(packet_dir: Path, lead: str, recipient: str | None, via: str | None,
                 wb: workbook.Workbook, sources: dict, html: str) -> Path:
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "message.html").write_text(html, encoding="utf-8")
    (packet_dir / "envelope.json").write_text(json.dumps({
        "lead": lead, "recipient": recipient, "resolved_via": via,
        "week_ending": str(wb.week_ending), "workbook_sha256": wb.sha256, "sources": sources,
    }, indent=2) + "\n")
    return packet_dir


def prepare(data_dir: Path, out_dir: Path, ledger: Path) -> tuple[int, str]:
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    src = sources_for(data_dir, ledger)

    # G1 runs on the sources BEFORE anything is built. A stale week builds nothing.
    why, wb = gate.freshness(src["workbook"], src["announcement"])
    if why:
        note = {"status": "refused", "rule": "G1", "reasons": why, "messages_built": 0}
        (out_dir / "run.json").write_text(json.dumps(note, indent=2) + "\n")
        return 1, "REFUSED  G1 freshness - nothing built, nobody messaged\n" + "\n".join(f"  {w}" for w in why)

    roster = json.loads(Path(src["roster"]).read_text())
    directory = json.loads(Path(src["directory"]).read_text())
    lines, skipped, verdicts, sites, via_dir = [], [], [], 0, 0
    for lead, rows in sorted(wb.by_lead().items()):
        res = resolve(lead, wb.lead_ids, roster, directory)
        if res.status != "resolved":
            skipped.append({"lead": lead, "sites": len(rows), "reason": res.reason})
            continue
        via_dir += res.via == "directory"
        pdir = write_packet(out_dir / slug(lead), lead, res.address, res.via, wb, src,
                            render.render(lead, rows, wb.week_ending))
        v = gate.grade(pdir)
        (pdir / "grading.json").write_text(json.dumps(v.to_json(), indent=2) + "\n")
        verdicts.append(v)
        sites += len(rows)
        lines.append(v.line())

    ok = all(v.passed for v in verdicts)
    note = {"status": "ready" if ok else "refused", "week_ending": str(wb.week_ending),
            "leads_in_workbook": len(wb.by_lead()), "messages_built": len(verdicts),
            "messages_passing": sum(v.passed for v in verdicts), "sites_covered": sites,
            "resolved_via_directory": via_dir, "skipped": skipped}
    (out_dir / "run.json").write_text(json.dumps(note, indent=2) + "\n")
    lines.append("")
    lines.append(f"week ending {wb.week_ending}: {note['messages_passing']}/{len(verdicts)} messages pass, "
                 f"{sites} of {len(wb.sites)} sites covered, {via_dir} resolved via directory")
    for s in skipped:
        lines.append(f"SKIPPED  {s['lead']} ({s['sites']} sites): {s['reason']}")
    return (0 if ok else 1), "\n".join(lines)


def send(out_dir: Path, now: str | None = None) -> tuple[int, str]:
    """Re-grades every packet with G6 switched on, then hands passing messages to the
    transport. The transport here is an outbox directory; `_deliver` is the one function
    to swap for a real chat or mail API."""
    out_dir = Path(out_dir)
    now = now or dt.datetime.now().isoformat(timespec="seconds")
    sent, refused, lines = 0, 0, []
    for env_path in sorted(out_dir.glob("*/envelope.json")):
        pdir = env_path.parent
        v = gate.grade(pdir, mode="send")
        (pdir / "grading.json").write_text(json.dumps(v.to_json(), indent=2) + "\n")
        if not v.passed:
            refused += 1
            lines.append(v.line())
            continue
        env = json.loads(env_path.read_text())
        _deliver(out_dir / "outbox", env["recipient"], (pdir / "message.html").read_text(encoding="utf-8"))
        # Ledger is written per message, not per run: a crash at message 150 must not
        # re-send the first 149 on retry.
        ledger_path = Path(env["sources"]["ledger"])
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
        ledger[gate.ledger_key(env["week_ending"], env["workbook_sha256"], env["lead"])] = {
            "recipient": env["recipient"], "sent_at": now}
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
        sent += 1
    lines.append(f"sent {sent}, refused {refused}")
    return (1 if refused else 0), "\n".join(lines)


def _deliver(outbox: Path, recipient: str, html: str) -> None:
    outbox.mkdir(parents=True, exist_ok=True)
    (outbox / f"{recipient}.html").write_text(html, encoding="utf-8")
