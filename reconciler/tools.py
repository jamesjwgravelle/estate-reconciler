"""The tools the investigator agent may use. All are read-only.

Every result carries a `ref` ("document :: location"). The toolbox remembers each ref it has
handed out, so the agent's final citations can be checked against what it was actually shown.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from .models import Finding, Matter
from .retrieval import BM25, build_chunks


def ref(doc: str, locator: str) -> str:
    return f"{doc} :: {locator}"


SPECS = [
    {"type": "function", "function": {
        "name": "search_documents",
        "description": "Full-text search over every document, ledger row and bank line in the file. "
                       "Returns the best-matching passages with their refs.",
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query": {"type": "string", "description": "Keywords, e.g. a payee, a document name, an address"}}}}},
    {"type": "function", "function": {
        "name": "find_transactions",
        "description": "List transactions from the executor's accounts or the bank record, filtered by "
                       "date range, amount range and/or text in the description. Use it to look for "
                       "split payments, reversals and timing differences.",
        "parameters": {"type": "object", "required": ["source"], "properties": {
            "source": {"type": "string", "enum": ["accounts", "bank"]},
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            "min_amount": {"type": "number"},
            "max_amount": {"type": "number"},
            "text": {"type": "string", "description": "Case-insensitive text the description must contain"}}}}},
    {"type": "function", "function": {
        "name": "add_amounts",
        "description": "Add dollar amounts exactly. Always use this instead of adding in your head.",
        "parameters": {"type": "object", "required": ["amounts"], "properties": {
            "amounts": {"type": "array", "items": {"type": "number"}}}}}},
    {"type": "function", "function": {
        "name": "submit_verdict",
        "description": "End the investigation. Call exactly once, when you have looked where an "
                       "explanation would be.",
        "parameters": {"type": "object", "required": ["verdict", "explanation", "citations"], "properties": {
            "verdict": {"type": "string", "enum": ["explained", "stands", "needs_human"]},
            "explanation": {"type": "string", "description": "Two or three sentences on what the documents show"},
            "citations": {"type": "array", "items": {"type": "string"},
                          "description": "Refs exactly as returned by the tools"}}}}},
]


class Toolbox:
    def __init__(self, matter: Matter, finding: Finding | None = None):
        self.m = matter
        self.index = BM25(build_chunks(matter, []))     # other findings are deliberately not searchable
        self.seen: dict[str, str] = {}                  # ref -> text shown
        self.original: set[str] = set()                 # refs already in the finding's evidence
        if finding:
            for ev in finding.evidence:
                r = ref(ev.doc, ev.locator)
                self.seen[r] = ev.quote
                self.original.add(r)

    def call(self, name: str, args: dict):
        try:
            if name == "search_documents":
                return self._search(str(args["query"]))
            if name == "find_transactions":
                return self._find(**args)
            if name == "add_amounts":
                return {"total": f"{sum((Decimal(str(a)) for a in args['amounts']), Decimal(0)):.2f}"}
            return {"error": f"unknown tool {name}"}
        except (KeyError, TypeError, ValueError, InvalidOperation) as e:
            return {"error": f"bad arguments for {name}: {e}"}

    def _search(self, query: str) -> list[dict]:
        out = []
        for c in self.index.search(query, k=6):
            r = ref(c.doc, c.locator)
            self.seen[r] = c.text
            out.append({"ref": r, "text": c.text})
        return out

    def _find(self, source: str, date_from: str | None = None, date_to: str | None = None,
              min_amount: float | None = None, max_amount: float | None = None,
              text: str | None = None) -> list[dict]:
        if source not in ("accounts", "bank"):
            raise ValueError("source must be 'accounts' or 'bank'")
        rows = self.m.accounts if source == "accounts" else self.m.bank
        lo = date.fromisoformat(date_from) if date_from else date.min
        hi = date.fromisoformat(date_to) if date_to else date.max
        out = []
        for t in rows:
            if not lo <= t.date <= hi:
                continue
            if min_amount is not None and t.amount < Decimal(str(min_amount)):
                continue
            if max_amount is not None and t.amount > Decimal(str(max_amount)):
                continue
            if text and text.lower() not in t.description.lower():
                continue
            r = ref(t.doc, t.locator)
            self.seen[r] = t.cite().quote
            out.append({"ref": r, "date": t.date.isoformat(), "description": t.description,
                        "amount": f"{t.amount:.2f}", "direction": "money in" if t.direction == "in" else "money out"})
        return out[:25]
