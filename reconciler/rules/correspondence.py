"""What the correspondence says against what was actually produced."""
from __future__ import annotations

from ..checks import Config, check
from ..extract import DOC_TYPES, PENDING, PROMISE, statements, tokens
from ..models import Evidence, Finding, Matter
from ._common import fmt


@check
def check_correspondence(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    produced = {d.doc_type: d for d in m.texts if d.doc_type}
    if m.accounts:
        produced.setdefault("statement_of_accounts", None)
    if m.bank:
        produced.setdefault("bank_records", None)

    missing: dict[str, list[Evidence]] = {}
    pending: dict[str, list] = {}       # doc type -> [(letter date, evidence)]
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
                    pending.setdefault(dt, []).append((doc.date, s.cite()))

            # (c) dollar figures in letters that match nothing in the records
            for amt in s.amounts():
                if amt < cfg.letter_amount_floor or amt in known_amounts:
                    continue
                scored = [(len(tokens(s.text) & tokens(t.description)), t) for t in m.accounts]
                score, best = max(scored, key=lambda x: x[0], default=(0, None))
                if best is not None and score >= 2:
                    out.append(Finding(
                        "letter_vs_records", best.id, "medium",
                        f"Letter states {fmt(amt)}; the accounts record {fmt(best.amount)} for the same item",
                        f"A difference of {fmt(abs(amt - best.amount))} between the correspondence "
                        f"and accounts entry {best.id}.",
                        [s.cite(), best.cite()],
                        amount=abs(amt - best.amount),
                        plain=f"A letter gave {fmt(amt)} as the figure for \"{best.description}\". "
                              f"The accounts record {fmt(best.amount)}, a difference of {fmt(abs(amt - best.amount))}."))

    for dt, letters in pending.items():
        held, label = produced[dt], DOC_TYPES[dt][0]
        letters.sort(key=lambda x: x[0])
        first, last = letters[0][0], letters[-1][0]
        reprint = (f" The copy produced was reprinted on {held.reprinted}; the original issue date is {held.date}."
                   if held.reprinted else "")
        out.append(Finding(
            "timeline_contradiction", dt, "high",
            f"{len(letters)} letter(s) from {first} to {last} say the {label} is outstanding; it is dated {held.date}",
            f"The document in the production is dated {(first - held.date).days} days before the first letter "
            f"describing it as not yet received.{reprint}",
            [e for _, e in letters] + [Evidence(held.name, "header", f"dated {held.date}"
                                                + (f"; reprinted {held.reprinted}" if held.reprinted else ""))],
            plain=f"{'A letter' if len(letters) == 1 else str(len(letters)) + ' letters'} from the executor's lawyers, "
                  f"the first dated {first}, said the {label} had not yet arrived. The notice itself is dated "
                  f"{held.date}." + (f" The copy we were given is a reprint made on {held.reprinted}, which "
                                     "can make the notice look more recent than it is." if held.reprinted else "")))

    for dt, cites in missing.items():
        label = DOC_TYPES[dt][0]
        out.append(Finding(
            "missing_document", dt, "high",
            f"{label[0].upper() + label[1:]} referred to in correspondence but not produced",
            f"Correspondence says this document is enclosed or will be provided ({len(cites)} "
            "reference(s)); no such document is in the production reviewed.",
            cites,
            plain=f"The executor's lawyers wrote that they were enclosing or would send the {label}. "
                  "It is not among the documents we were given."))
    return out
