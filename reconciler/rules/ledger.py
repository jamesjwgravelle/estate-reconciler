"""Accounts against the bank record, entry by entry."""
from __future__ import annotations

from ..checks import Config, check
from ..models import Finding, Matter, Txn
from ._common import days, fmt, similar


@check
def reconcile_ledgers(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    open_bank = list(m.bank)
    open_acct = list(m.accounts)

    def take(entry: Txn, test) -> Txn | None:
        hits = [b for b in open_bank if b.direction == entry.direction and test(b)]
        if not hits:
            return None
        best = min(hits, key=lambda b: days(entry, b))
        open_bank.remove(best)
        open_acct.remove(entry)
        return best

    # Pass 1: clean matches. Run for every entry first so a clean match is never stolen.
    for e in list(open_acct):
        take(e, lambda b: b.amount == e.amount and days(e, b) <= cfg.exact_window_days)

    # Pass 2: same payee and timing, different amount.
    for e in list(open_acct):
        b = take(e, lambda b: similar(e.description, b.description)
                 and days(e, b) <= cfg.similar_window_days)
        if b:
            sign = 1 if e.direction == "out" else -1
            out.append(Finding(
                "amount_mismatch", e.id, "high",
                f"Accounts entry {e.id} differs from the bank record by {fmt(abs(e.amount - b.amount))}",
                f"The accounts report {fmt(e.amount)}; the bank record shows {fmt(b.amount)} "
                f"for what appears to be the same item.",
                [e.cite(), b.cite()],
                amount=abs(e.amount - b.amount), balance_effect=sign * (e.amount - b.amount),
                plain=f"The accounts give {fmt(e.amount)} for \"{e.description}\". "
                      f"The bank statements show {fmt(b.amount)}."))

    # Pass 3: same amount, but the dates are far apart.
    for e in list(open_acct):
        b = take(e, lambda b: b.amount == e.amount and days(e, b) <= cfg.late_window_days)
        if b:
            out.append(Finding(
                "date_mismatch", e.id, "low",
                f"Accounts entry {e.id} is dated {days(e, b)} days from the bank record",
                f"The accounts date this item {e.date}; the bank record shows {b.date}.",
                [e.cite(), b.cite()],
                amount=e.amount,
                plain=f"\"{e.description}\" ({fmt(e.amount)}) is dated {e.date} in the accounts "
                      f"and {b.date} at the bank, {days(e, b)} days apart."))

    for e in open_acct:
        paid = e.direction == "out"
        out.append(Finding(
            "unsupported_entry", e.id, "high",
            f"No bank transaction supports accounts entry {e.id} ({fmt(e.amount)})",
            "The accounts list this item but no corresponding movement appears in the bank "
            "record produced. A voucher, cheque image or other account statement would resolve it.",
            [e.cite()],
            amount=e.amount, balance_effect=e.amount if paid else -e.amount,
            plain=f"The accounts list a {'payment' if paid else 'receipt'} of {fmt(e.amount)} for "
                  f"\"{e.description}\". The bank statements we were given show no such transaction."))

    for b in open_bank:
        if b.amount < cfg.materiality:
            continue
        left = b.direction == "out"
        out.append(Finding(
            "undisclosed_transaction", b.id, "high",
            f"Bank transaction of {fmt(b.amount)} on {b.date} does not appear in the accounts",
            "The bank record shows this movement but the statement of accounts has no entry for it.",
            [b.cite()],
            amount=b.amount, balance_effect=-b.amount if left else b.amount,
            plain=f"The bank statements show {fmt(b.amount)} {'leaving' if left else 'entering'} the "
                  f"estate account on {b.date} (\"{b.description}\"). The accounts do not mention it."))
    return out
