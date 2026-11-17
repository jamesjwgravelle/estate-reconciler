"""Draft a document-request letter from the findings that survived investigation.

Template-based on purpose: the wording of a demand is the lawyer's call, and a draft built
from fixed language cannot introduce a fact that is not in the findings. Nothing is sent.
The wording for each finding type lives in catalog.py.
"""
from __future__ import annotations

from .catalog import info
from .models import Finding


def draft_request(findings: list[Finding], investigations: list) -> str:
    verdict = {(i.type, i.key): i.verdict for i in investigations}
    keep = [f for f in findings if verdict.get((f.type, f.key), "stands") != "explained"]
    lines = [
        "> DRAFT FOR LAWYER REVIEW. NOT SENT. Check every item against its source before use.",
        "",
        "Re: Request for documents and information",
        "",
        "We have reviewed the statement of accounts, the bank record and the correspondence "
        "produced to date. We ask for the following:",
        "",
    ]
    for n, f in enumerate(keep, start=1):
        sources = "; ".join(f"{e.doc}, {e.locator}" for e in f.evidence)
        flag = "  [reviewer: investigation was inconclusive]" if verdict.get((f.type, f.key)) == "needs_human" else ""
        lines += [f"{n}. {f.title}. {info(f.type).ask}{flag}",
                  f"   (Source: {sources})", ""]
    lines.append("We would be grateful for a response within 30 days.")
    return "\n".join(lines) + "\n"
