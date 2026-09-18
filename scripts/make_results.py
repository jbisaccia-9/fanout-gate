"""Regenerate RESULTS.md from real command output. Run from the repo root."""
import datetime
import shutil
import subprocess
import sys
from pathlib import Path

NOW = "2026-09-15T08:00:00"
STEPS = [
    ("Unit tests", "python -m pytest -q", 0),
    ("Seed the synthetic week", "python -m fanoutgate seed data", 0),
    ("Prepare: G1 on the sources, then one graded packet per resolvable lead", "python -m fanoutgate prepare data --out out/run", 0),
    ("Send: first attempt delivers and writes the ledger per message", f"python -m fanoutgate send out/run --now {NOW}", 0),
    ("Send: the retry is refused, every message, by G6", "python -m fanoutgate send out/run", 1),
    ("Reconcile: the documented action-plan formula vs. what the workbook stores", "python -m fanoutgate reconcile data", 0),
    ("Build the counterexamples", "python -m fanoutgate counterexamples out/cx --data data", 0),
    ("Gate refuses every counterexample, each for its own rule", "python -m fanoutgate check-dir out/cx --send", 1),
]

shutil.rmtree("out", ignore_errors=True)
shutil.rmtree("data", ignore_errors=True)
out = [f"# Results\n\nGenerated {datetime.date.today()} by `scripts/make_results.py` — every block below is captured command output, not prose.\n"]
ok_all = True
for title, cmd, want in STEPS:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    good = (r.returncode == 0) if want == 0 else (r.returncode != 0)
    ok_all &= good
    exp = "exit 0" if want == 0 else "expected non-zero exit"
    body = (r.stdout + r.stderr).strip()
    if "pytest" in cmd:
        body = "\n".join(l for l in body.splitlines() if not l.startswith("=") or "passed" in l)
    out.append(f"## {title}\n\n`{cmd}` — {exp}, {'OK' if good else 'UNEXPECTED'}\n\n```\n{body}\n```\n")
Path("RESULTS.md").write_text("\n".join(out), encoding="utf-8")
print("wrote RESULTS.md", "OK" if ok_all else "WITH UNEXPECTED RESULTS")
sys.exit(0 if ok_all else 1)
