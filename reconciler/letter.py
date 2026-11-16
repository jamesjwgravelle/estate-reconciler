"""Draft a document-request letter from the findings that survived investigation.

Template-based on purpose: the wording of a demand is the lawyer's call, and a draft built
from fixed language cannot introduce a fact that is not in the findings. Nothing is sent.
"""
from __future__ import annotations

from .agent import Investigation
from .models import Finding

ASK = {
    "amount_mismatch": "Please explain the difference and produce the invoice and the cheque image or payment record.",
    "unsupported_entry": "Please produce the voucher for this item and identify the account from which it was paid.",
    "undisclosed_transaction": "Please identify the payee and purpose of this transaction and explain why it does not appear in the accounts.",
    "arithmetic_error": "Please provide a corrected summary of accounts.",
    "balance_mismatch": "Please provide a reconciliation of the stated balance to the bank balance.",
    "missing_document": "Please produce this document.",
    "timeline_contradiction": "Please confirm the date on which this document was received, and by whom.",
    "letter_vs_records": "Please confirm which figure is correct and produce the supporting document.",
    "compensation_review": "Please provide the basis for the compensation claimed, including any record of time spent.",
    "date_mismatch": "Please confirm the date on which this payment was made.",
}


def draft_request(findings: list[Finding], investigations: list[Investigation]) -> str:
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
        lines += [f"{n}. {f.title}. {ASK.get(f.type, 'Please provide an explanation.')}{flag}",
                  f"   (Source: {sources})", ""]
    lines.append("We would be grateful for a response within 30 days.")
    return "\n".join(lines) + "\n"
