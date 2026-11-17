"""Command line:

    python -m reconciler analyze <matter>        checks only, then the reports (no model needed)
    python -m reconciler investigate <matter>    checks, the agent on each finding, then the reports
    python -m reconciler report <matter>         rebuild the reports from a saved investigation
    python -m reconciler ask <matter> "question"

Reports are written to --out: report_lawyer.html, report_client.html, schedule.csv,
draft_request_letter.md, findings.json (and investigations.json after `investigate`).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import llm
from .agent import investigate_all
from .checks import run_all
from .ingest import load_matter
from .report import load_investigations, money, write_all, write_json
from .retrieval import ask
from .summary import totals


def main() -> None:
    p = argparse.ArgumentParser(prog="reconciler")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, text in (("analyze", "run the checks and write the reports"),
                       ("investigate", "run the checks, investigate each finding, write the reports"),
                       ("report", "rebuild the reports, using investigations.json in --out if present")):
        a = sub.add_parser(name, help=text)
        a.add_argument("matter")
        a.add_argument("--out", default="out")
        a.add_argument("--title", help="name of the matter for the report headings (default: folder name)")
    q = sub.add_parser("ask", help="ask a question of the matter")
    q.add_argument("matter")
    q.add_argument("question")
    args = p.parse_args()

    matter = load_matter(args.matter)
    findings = run_all(matter)

    if args.cmd == "ask":
        result = ask(matter, findings, args.question)
        print(result["answer"] + "\n" if result["answer"]
              else "(No language model configured; showing the most relevant passages.)\n")
        for i, c in enumerate(result["passages"], start=1):
            print(f"[{i}] {c.doc}, {c.locator}: {c.text}")
        return

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    title = args.title or Path(args.matter).resolve().name
    invs = None

    if args.cmd == "investigate":
        if not llm.configured():
            sys.exit("investigate needs a model: set RECONCILER_LLM_BASE_URL and RECONCILER_LLM_MODEL (see README)")
        invs = investigate_all(
            findings, matter, llm.Client(), reviewer=llm.reviewer_client(),
            progress=lambda f, i: print(f"[{i.verdict:<11}] {f.type:<24} {f.key}" + (f"  ({i.note})" if i.note else "")))
        write_json(invs, out / "investigations.json")
        print()
    elif args.cmd == "report" and (out / "investigations.json").exists():
        invs = load_investigations(out / "investigations.json")
        print(f"using {out / 'investigations.json'}\n")
    else:
        for f in findings:
            amount = money(f.amount) if f.amount is not None else ""
            print(f"[{f.severity:<6}] {f.type:<24} {amount:>12}  {f.title}")
        print()

    t = totals(findings, invs)
    print(f"{t['open_count']} open items, {money(t['amount_in_question'])} in question"
          + ("" if invs else " (not yet investigated)"))
    for path in write_all(matter, findings, invs, out, title):
        print(f"  {path}")


if __name__ == "__main__":
    main()
