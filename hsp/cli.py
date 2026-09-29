"""hsp CLI — validate decisioning-expression artifacts against the grammar."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hsp.core.report import Status, ValidationReport
from hsp.grammars.json_dsl import JsonDslGrammar

_PLUGINS = {"decisioning-expression": JsonDslGrammar}


def _print_report(path: str, report: ValidationReport) -> None:
    verdict = "PASS" if report.ok else "FAIL"
    print(f"{verdict}  {path}")
    for tier in report.tiers:
        mark = {Status.PASS: "  ok ", Status.FAIL: " FAIL", Status.SKIP: " skip"}[tier.status]
        print(f"  [{mark}] tier {tier.tier} {tier.name}")
        for issue in tier.issues:
            loc = f" @{issue.path}" if issue.path else ""
            print(f"         {issue.severity} {issue.code}{loc}: {issue.message}")


def main() -> int:
    ap = argparse.ArgumentParser(prog="hsp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "validate-dir", "eval"):
        p = sub.add_parser(name)
        p.add_argument("path", type=Path)
        p.add_argument("--grammar", default="decisioning-expression")
    sub.choices["eval"].add_argument("--case", type=Path, required=True,
                                   help="synthetic report JSON to evaluate against")
    args = ap.parse_args()

    plugin = _PLUGINS[args.grammar]()
    paths = ([args.path] if args.cmd != "validate-dir"
             else sorted(args.path.glob("*.json")))

    ok = True
    for path in paths:
        report = plugin.validate(path.read_text())
        _print_report(str(path), report)
        ok &= report.ok
        if args.cmd == "eval" and report.ok:
            case = json.loads(args.case.read_text())
            print(f"  eval -> {json.dumps(plugin.evaluate(path.read_text(), case))}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
