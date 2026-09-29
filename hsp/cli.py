"""hsp CLI — validate artifacts, generate proposals, run eval cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hsp.corpus.store import Corpus
from hsp.core.report import Status, ValidationReport
from hsp.grammars.json_dsl import JsonDslGrammar
from hsp.provider.base import Provider

_PLUGINS = {"decisioning-expression": JsonDslGrammar}
_DEFAULT_CORPUS = "corpus/exemplars/json_dsl"


def _print_report(path: str, report: ValidationReport) -> None:
    verdict = "PASS" if report.ok else "FAIL"
    print(f"{verdict}  {path}")
    for tier in report.tiers:
        mark = {Status.PASS: "  ok ", Status.FAIL: " FAIL", Status.SKIP: " skip"}[tier.status]
        print(f"  [{mark}] tier {tier.tier} {tier.name}")
        for issue in tier.issues:
            loc = f" @{issue.path}" if issue.path else ""
            print(f"         {issue.severity} {issue.code}{loc}: {issue.message}")


def _provider(name: str, model: str | None) -> Provider:
    if name == "ollama":
        from hsp.provider.ollama import OllamaProvider
        return OllamaProvider(model=model)
    raise SystemExit(f"unknown provider {name!r} (choices: ollama)")


def main() -> int:
    ap = argparse.ArgumentParser(prog="hsp")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("validate", "validate-dir", "eval-artifact"):
        p = sub.add_parser(name)
        p.add_argument("path", type=Path)
        p.add_argument("--grammar", default="decisioning-expression")
    sub.choices["eval-artifact"].add_argument(
        "--case", type=Path, required=True,
        help="synthetic report JSON to evaluate against")

    g = sub.add_parser("generate")
    g.add_argument("requirement")
    g.add_argument("--grammar", default="decisioning-expression")
    g.add_argument("--corpus", type=Path, default=Path(_DEFAULT_CORPUS))
    g.add_argument("--model", default=None)
    g.add_argument("--provider", default="ollama")
    g.add_argument("--refs", nargs="*", default=[], help="source_refs e.g. req:AZDO-1")
    g.add_argument("--out", type=Path, default=None, help="bundle output dir")
    g.add_argument("--max-attempts", type=int, default=3)

    e = sub.add_parser("eval")
    e.add_argument("--grammar", default="decisioning-expression")
    e.add_argument("--cases", type=Path, default=Path("eval/cases"))
    e.add_argument("--corpus", type=Path, default=Path(_DEFAULT_CORPUS))
    e.add_argument("--model", default=None)
    e.add_argument("--provider", default="ollama")

    args = ap.parse_args()
    plugin = _PLUGINS[args.grammar]()

    if args.cmd == "generate":
        from hsp.pipeline import generate
        res = generate(
            args.requirement, plugin=plugin,
            corpus=Corpus.load(args.corpus),
            provider=_provider(args.provider, args.model),
            source_refs=args.refs, max_attempts=args.max_attempts,
            out_dir=args.out)
        b = res.bundle
        print(json.dumps(b.artifact, indent=2))
        print(f"\nstatus={b.status} attempts={b.provenance.attempts} "
              f"digest={b.digest or 'n/a'}")
        if res.bundle_dir:
            print(f"bundle -> {res.bundle_dir}")
        return 0 if b.status == "PROPOSED" else 1

    if args.cmd == "eval":
        from hsp.eval.harness import run_cases
        rep = run_cases(args.cases, plugin=plugin,
                        corpus=Corpus.load(args.corpus),
                        provider=_provider(args.provider, args.model))
        for c in rep.cases:
            print(f"{'PASS' if c.valid and c.structural_match else 'FAIL'} {c.case_id} "
                  f"attempts={c.attempts} golden={c.golden_pass}/{c.golden_total} "
                  f"{c.detail}")
        print(json.dumps(rep.summary(), indent=2))
        return 0

    paths = ([args.path] if args.cmd != "validate-dir"
             else sorted(args.path.glob("*.json")))
    ok = True
    for path in paths:
        report = plugin.validate(path.read_text())
        _print_report(str(path), report)
        ok &= report.ok
        if args.cmd == "eval-artifact" and report.ok:
            case = json.loads(args.case.read_text())
            print(f"  eval -> {json.dumps(plugin.evaluate(path.read_text(), case))}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
