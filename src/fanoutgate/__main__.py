from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import counterexamples, gate, pipeline, reconcile, seed, workbook


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fanoutgate", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("seed", help="write the synthetic week (workbook, announcement, roster, directory)")
    a.add_argument("data")
    a = sub.add_parser("prepare", help="G1 on the sources, then build and grade one packet per lead")
    a.add_argument("data"); a.add_argument("--out", default="out/run"); a.add_argument("--ledger", default="out/ledger.json")
    a = sub.add_parser("send", help="re-grade with G6, deliver what passes, write the ledger per message")
    a.add_argument("run"); a.add_argument("--now", default=None, help="fixed timestamp, for reproducible output")
    a = sub.add_parser("check-dir", help="grade every packet in a directory; exit 1 if any is refused")
    a.add_argument("dir"); a.add_argument("--send", action="store_true", help="include G6")
    a = sub.add_parser("counterexamples", help="build the six packets that must be refused")
    a.add_argument("out"); a.add_argument("--data", default="data")
    a = sub.add_parser("reconcile", help="measure the documented action-plan formula against the stored text")
    a.add_argument("data")
    args = ap.parse_args(argv)

    if args.cmd == "seed":
        print(f"wrote {seed.write(Path(args.data))}")
        return 0
    if args.cmd == "prepare":
        code, text = pipeline.prepare(Path(args.data), Path(args.out), Path(args.ledger))
    elif args.cmd == "send":
        code, text = pipeline.send(Path(args.run), args.now)
    elif args.cmd == "check-dir":
        verdicts = gate.check_dir(Path(args.dir), "send" if args.send else "build")
        bad = sum(not v.passed for v in verdicts)
        text = "\n".join(v.line() for v in verdicts) + f"\n\n{len(verdicts) - bad} pass, {bad} refused"
        code = 1 if bad or not verdicts else 0
    elif args.cmd == "counterexamples":
        names = counterexamples.build(Path(args.data), Path(args.out))
        text = "\n".join(f"{n:<26} {counterexamples.DESCRIPTIONS[n]}" for n in names)
        code = 0
    else:
        text = reconcile.render_report(reconcile.report(workbook.read(workbook.find_workbook(Path(args.data)))))
        code = 0
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
