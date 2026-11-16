"""The reconciliation checks.

Anything involving arithmetic or matching is done deterministically here, never by a language
model. Each check returns Findings with Evidence; a finding is a discrepancy to follow up on,
not a conclusion about anyone's conduct.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .extract import DOC_TYPES, PENDING, PROMISE, statements, tokens
from .models import Evidence, Finding, Matter, Txn


@dataclass
class Config:
    exact_window_days: int = 5        # same amount, dates this close: treated as the same item
    similar_window_days: int = 10     # similar payee, dates this close, different amount: mismatch
    late_window_days: int = 60        # same amount but dates this far apart: date discrepancy
    materiality: Decimal = Decimal("25.00")       # bank items below this are not flagged
    letter_amount_floor: Decimal = Decimal("1000")
    # Rule of thumb for executor compensation: a percentage of receipts plus a percentage of
    # disbursements. 2.5% + 2.5% is the customary Ontario starting point; set per jurisdiction.
    comp_rate_receipts: Decimal = Decimal("0.025")
    comp_rate_disbursements: Decimal = Decimal("0.025")


def _fmt(x: Decimal) -> str:
    return f"${x:,.2f}"


def _days(a: Txn, b: Txn) -> int:
    return abs((a.date - b.date).days)


def _similar(a: str, b: str) -> bool:
    return len(tokens(a) & tokens(b)) >= 1


# --- 1. accounts vs bank ----------------------------------------------------------------------

def reconcile_ledgers(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    open_bank = list(m.bank)
    open_acct = list(m.accounts)

    def take(entry: Txn, test) -> Txn | None:
        hits = [b for b in open_bank if b.direction == entry.direction and test(b)]
        if not hits:
            return None
        best = min(hits, key=lambda b: _days(entry, b))
        open_bank.remove(best)
        open_acct.remove(entry)
        return best

    # Pass 1: clean matches. Run for every entry first so a clean match is never stolen.
    for e in list(open_acct):
        take(e, lambda b: b.amount == e.amount and _days(e, b) <= cfg.exact_window_days)

    # Pass 2: same payee and timing, different amount.
    for e in list(open_acct):
        b = take(e, lambda b: _similar(e.description, b.description)
                 and _days(e, b) <= cfg.similar_window_days)
        if b:
            out.append(Finding(
                "amount_mismatch", e.id, "high",
                f"Accounts entry {e.id} differs from the bank record by {_fmt(abs(e.amount - b.amount))}",
                f"The accounts report {_fmt(e.amount)}; the bank record shows {_fmt(b.amount)} "
                f"for what appears to be the same item.",
                [e.cite(), b.cite()]))

    # Pass 3: same amount, but the dates are far apart.
    for e in list(open_acct):
        b = take(e, lambda b: b.amount == e.amount and _days(e, b) <= cfg.late_window_days)
        if b:
            out.append(Finding(
                "date_mismatch", e.id, "low",
                f"Accounts entry {e.id} is dated {_days(e, b)} days from the bank record",
                f"The accounts date this item {e.date}; the bank record shows {b.date}.",
                [e.cite(), b.cite()]))

    for e in open_acct:
        out.append(Finding(
            "unsupported_entry", e.id, "high",
            f"No bank transaction supports accounts entry {e.id} ({_fmt(e.amount)})",
            "The accounts list this item but no corresponding movement appears in the bank "
            "record produced. A voucher, cheque image or other account statement would resolve it.",
            [e.cite()]))

    for b in open_bank:
        if b.amount < cfg.materiality:
            continue
        out.append(Finding(
            "undisclosed_transaction", b.id, "high",
            f"Bank transaction of {_fmt(b.amount)} on {b.date} does not appear in the accounts",
            "The bank record shows this movement but the statement of accounts has no entry for it.",
            [b.cite()]))
    return out


# --- 2. the accounts' own arithmetic ----------------------------------------------------------

def check_arithmetic(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    sums = {
        "total_receipts": sum((t.amount for t in m.accounts if t.direction == "in"), Decimal(0)),
        "total_disbursements": sum((t.amount for t in m.accounts if t.direction == "out"), Decimal(0)),
    }
    for key, computed in sums.items():
        if key in m.summary:
            stated, ev = m.summary[key]
            if stated != computed:
                out.append(Finding(
                    "arithmetic_error", key, "high",
                    f"Stated {key.replace('_', ' ')} is off by {_fmt(abs(stated - computed))}",
                    f"The summary states {_fmt(stated)}; the itemised entries add up to {_fmt(computed)}.",
                    [ev]))

    if "balance_on_hand" in m.summary and m.bank_closing is not None:
        stated, ev = m.summary["balance_on_hand"]
        # Small bank items we chose not to flag (e.g. monthly fees) legitimately explain a gap.
        small = sum((b.amount if b.direction == "out" else -b.amount
                     for b in m.bank if b.amount < cfg.materiality), Decimal(0))
        expected = m.bank_closing + small
        if abs(stated - expected) > Decimal("0.01"):
            out.append(Finding(
                "balance_mismatch", "balance_on_hand", "high",
                f"Stated balance on hand differs from the bank balance by {_fmt(abs(stated - expected))}",
                f"The summary states {_fmt(stated)}; the bank record closes at {_fmt(m.bank_closing)} "
                f"(with {_fmt(small)} of sub-materiality bank items allowed for).",
                [ev, Evidence(m.bank_doc or "bank record", "last line", f"closing balance {_fmt(m.bank_closing)}")]))
    return out


# --- 3. executor compensation -----------------------------------------------------------------

def check_compensation(m: Matter, cfg: Config) -> list[Finding]:
    comp = [t for t in m.accounts if t.direction == "out" and "compensation" in t.description.lower()]
    if not comp:
        return []
    claimed = sum((t.amount for t in comp), Decimal(0))
    receipts = sum((t.amount for t in m.accounts if t.direction == "in"), Decimal(0))
    disb = sum((t.amount for t in m.accounts if t.direction == "out" and t not in comp), Decimal(0))
    guide = (receipts * cfg.comp_rate_receipts + disb * cfg.comp_rate_disbursements).quantize(Decimal("0.01"))
    if claimed <= guide:
        return []
    return [Finding(
        "compensation_review", comp[0].id, "medium",
        f"Executor compensation of {_fmt(claimed)} exceeds the configured guideline of {_fmt(guide)}",
        f"Guideline used: {cfg.comp_rate_receipts:.1%} of receipts ({_fmt(receipts)}) plus "
        f"{cfg.comp_rate_disbursements:.1%} of other disbursements ({_fmt(disb)}). This is a "
        "starting point for review, not a cap; courts adjust for the work actually done.",
        [t.cite() for t in comp])]


# --- 4. what the correspondence says vs what was produced --------------------------------------

def check_correspondence(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    produced = {d.doc_type: d for d in m.texts if d.doc_type}
    if m.accounts:
        produced.setdefault("statement_of_accounts", None)
    if m.bank:
        produced.setdefault("bank_records", None)

    missing: dict[str, list[Evidence]] = {}
    known_amounts = {t.amount for t in m.accounts} | {t.amount for t in m.bank}

    for doc in m.texts:
        if doc.doc_type:          # only correspondence makes representations we test
            continue
        for s in statements(doc):
            for dt in s.doc_types():
                label = DOC_TYPES[dt][0]
                # (a) promised or "enclosed", but not in the production
                if PROMISE.search(s.text) and dt not in produced:
                    missing.setdefault(dt, []).append(s.cite())
                # (b) said to be outstanding after the document's own date
                held = produced.get(dt)
                if (PENDING.search(s.text) and held is not None and held.date and doc.date
                        and doc.date > held.date):
                    gap = (doc.date - held.date).days
                    out.append(Finding(
                        "timeline_contradiction", dt, "high",
                        f"Letter of {doc.date} says the {label} is outstanding; it is dated {held.date}",
                        f"The document in the production is dated {gap} days before the letter "
                        "describing it as not yet received.",
                        [s.cite(), Evidence(held.name, "header", f"dated {held.date}")]))

            # (c) dollar figures in letters that match nothing in the records
            for amt in s.amounts():
                if amt < cfg.letter_amount_floor or amt in known_amounts:
                    continue
                scored = [(len(tokens(s.text) & tokens(t.description)), t) for t in m.accounts]
                score, best = max(scored, key=lambda x: x[0], default=(0, None))
                if best is not None and score >= 2:
                    out.append(Finding(
                        "letter_vs_records", best.id, "medium",
                        f"Letter states {_fmt(amt)}; the accounts record {_fmt(best.amount)} for the same item",
                        f"A difference of {_fmt(abs(amt - best.amount))} between the correspondence "
                        f"and accounts entry {best.id}.",
                        [s.cite(), best.cite()]))

    for dt, cites in missing.items():
        out.append(Finding(
            "missing_document", dt, "high",
            f"{DOC_TYPES[dt][0][0].upper() + DOC_TYPES[dt][0][1:]} referred to in correspondence but not produced",
            f"Correspondence says this document is enclosed or will be provided ({len(cites)} "
            "reference(s)); no such document is in the production reviewed.",
            cites))
    return out


CHECKS = [reconcile_ledgers, check_arithmetic, check_compensation, check_correspondence]
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def run_all(m: Matter, cfg: Config | None = None) -> list[Finding]:
    cfg = cfg or Config()
    findings = [f for check in CHECKS for f in check(m, cfg)]
    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.type, f.key))
