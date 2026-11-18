"""Load a matter folder.

Conventions (kept deliberately simple; see README):
  accounts*.csv          executor's statement of accounts: entry_id,date,type,description,amount
  bank*.csv              bank record: date,description,debit,credit,balance
  accounts_summary*.txt  the totals the executor reports ("Total receipts: $...")
  anything else .txt/.md/.pdf, in any subfolder: narrative documents (letters, notices, the will)
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .extract import classify_doc
from .models import Evidence, Matter, TextDoc, Txn

MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)")
ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
SUMMARY_KEYS = {
    "total receipts": "total_receipts",
    "total disbursements": "total_disbursements",
    "balance on hand": "balance_on_hand",
}


def money(s: str) -> Decimal:
    return Decimal(s.replace("$", "").replace(",", "").strip() or "0")


def parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _read_text(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency
        except ImportError as e:
            raise RuntimeError(f"{path.name}: install pypdf to read PDFs") from e
        text = "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        return text.splitlines()
    return path.read_text(encoding="utf-8").splitlines()


REPRINT = re.compile(r"reprint|reproduc|copy (made|printed)", re.I)


def _doc_date(lines: list[str]) -> Optional[date]:
    """The document's own date: a 'Date:' or 'Date issued:' header line with an ISO date.

    A line describing a reprint or reproduction is skipped. A copy of a notice reprinted in
    July is still a notice issued in December, and reading the reprint date as the issue date
    would hide exactly the contradiction the timeline check exists to find."""
    for line in lines[:15]:
        if line.lower().startswith("date") and not REPRINT.search(line):
            m = ISO_DATE.search(line)
            if m:
                return parse_date(m.group(1))
    return None


def _reprint_date(lines: list[str]) -> Optional[date]:
    for line in lines[:15]:
        if REPRINT.search(line):
            m = ISO_DATE.search(line)
            if m:
                return parse_date(m.group(1))
    return None


def load_matter(root: str | Path) -> Matter:
    root = Path(root)
    m = Matter(root=str(root))
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = str(path.relative_to(root))
        name, suffix = path.name.lower(), path.suffix.lower()

        if suffix == ".csv" and name.startswith("accounts"):
            with path.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    kind = row["type"].strip().lower()
                    m.accounts.append(Txn(
                        id=row["entry_id"].strip(), date=parse_date(row["date"]),
                        direction="in" if kind.startswith("receipt") else "out",
                        description=row["description"].strip(), amount=money(row["amount"]),
                        doc=rel, locator=f"row {row['entry_id'].strip()}"))

        elif suffix == ".csv" and name.startswith("bank"):
            m.bank_doc = rel
            with path.open(newline="", encoding="utf-8") as f:
                for i, row in enumerate(csv.DictReader(f), start=2):  # line 1 is the header
                    debit, credit = money(row["debit"]), money(row["credit"])
                    d = parse_date(row["date"])
                    amount = debit if debit else credit
                    m.bank.append(Txn(
                        id=f"{d.isoformat()}:{amount:.2f}", date=d,
                        direction="out" if debit else "in",
                        description=row["description"].strip(), amount=amount,
                        doc=rel, locator=f"line {i}"))
                    if row.get("balance", "").strip():
                        m.bank_closing = money(row["balance"])

        elif suffix == ".txt" and name.startswith("accounts_summary"):
            for i, line in enumerate(_read_text(path), start=1):
                for label, key in SUMMARY_KEYS.items():
                    if line.lower().startswith(label):
                        found = MONEY.search(line)
                        if found:
                            m.summary[key] = (money(found.group(1)), Evidence(rel, f"line {i}", line.strip()))

        elif suffix in (".txt", ".md", ".pdf"):
            lines = _read_text(path)
            m.texts.append(TextDoc(name=rel, lines=lines,
                                   doc_type=classify_doc(rel, lines), date=_doc_date(lines),
                                   reprinted=_reprint_date(lines)))
    return m
