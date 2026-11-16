"""Command line:

    python -m reconciler analyze <matter>            first-pass checks and memo
    python -m reconciler investigate <matter>        checks, then the agent on each finding
    python -m reconciler ask <matter> "question"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import llm
from .agent import investigate_all
from .checks import run_all
from .ingest import load_matter
from .letter import draft_request
from .report import write_html, write_json
from .retrieval import ask


def main() -> None:
    p = argparse.ArgumentParser(prog="reconciler")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, text in (("analyze", "run all checks and write a memo"),
                       ("investigate", "run the checks, investigate each finding, draft a request letter")):
        a = sub.add_parser(name, help=text)
        a.add_argument("matter")
        a.add_argument("--out", default="out")
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
    write_json(findings, out / "findings.json")

    if args.cmd == "analyze":
        write_html(matter, findings, out / "memo.html")
        for f in findings:
            print(f"[{f.severity:<6}] {f.type:<24} {f.title}")
        print(f"\n{len(findings)} findings -> {out / 'memo.html'}")
        return

    if not llm.configured():
        sys.exit("investigate needs a model: set RECONCILER_LLM_BASE_URL and RECONCILER_LLM_MODEL (see README)")
    invs = investigate_all(
        findings, matter, llm.Client(),
        progress=lambda f, i: print(f"[{i.verdict:<11}] {f.type:<24} {f.key}" + (f"  ({i.note})" if i.note else "")))
    write_json(invs, out / "investigations.json")
    write_html(matter, findings, out / "memo.html", invs)
    (out / "draft_request_letter.md").write_text(draft_request(findings, invs), encoding="utf-8")
    print(f"\n-> {out / 'memo.html'}, {out / 'investigations.json'}, {out / 'draft_request_letter.md'}")


if __name__ == "__main__":
    main()
