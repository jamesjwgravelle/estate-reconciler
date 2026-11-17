"""Write the outputs: a lawyer's report, a client summary, a schedule (CSV) and JSON.

All figures come from summary.py. Nothing here calls a model. Both reports number the items
the same way, so "item 4" in the client summary is item 4 in the lawyer's report.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from decimal import Decimal
from html import escape
from pathlib import Path

from .catalog import info
from .letter import draft_request
from .models import Evidence, Finding, Matter
from .summary import OPEN, balance_bridge, statuses, totals

CSS = """
body{font:15px/1.5 Georgia,serif;max-width:880px;margin:40px auto;padding:0 20px;color:#1c1c1c}
h1{font-size:24px;margin-bottom:4px} h2{font-size:18px;margin-top:34px;border-bottom:1px solid #ddd;padding-bottom:4px}
.sub{color:#555;margin-top:0} .draft{font:12px Arial,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#9b2c2c}
.note{background:#f6f4ee;border-left:3px solid #8a7a4a;padding:10px 14px;font-size:14px}
.head{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0}
.box{flex:1;min-width:150px;border:1px solid #ddd;border-radius:6px;padding:12px 16px}
.box b{display:block;font-size:24px} .box span{font:12px Arial,sans-serif;color:#555}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #e5e5e5;vertical-align:top}
th{font:12px Arial,sans-serif;color:#555} td.n,th.n{text-align:right;white-space:nowrap}
tr.tot td{font-weight:bold;border-top:2px solid #999}
.f{border:1px solid #ddd;border-radius:6px;padding:14px 18px;margin:16px 0}
.f h3{font-size:16px;margin:0 0 6px} .amt{float:right;font-weight:bold}
.tag{font:11px/1 Arial,sans-serif;text-transform:uppercase;letter-spacing:.06em;padding:3px 7px;
border-radius:3px;color:#fff;margin-right:8px;vertical-align:2px}
.high{background:#9b2c2c}.medium{background:#b7791f}.low{background:#4a5568}
.type{font:12px Arial,sans-serif;color:#666}
blockquote{margin:8px 0 0;padding:6px 12px;border-left:3px solid #ccc;font-size:14px;background:#fafafa}
cite{display:block;font:12px Arial,sans-serif;color:#666;font-style:normal}
.inv{margin-top:14px;padding:10px 14px;border-radius:4px;font-size:14px}
.inv b{font:12px Arial,sans-serif;text-transform:uppercase;letter-spacing:.05em}
.explained{background:#edf7ed}.stands{background:#fdeeee}.needs_human{background:#fdf6e3}
.small{font-size:13px;color:#555}
@media print{body{margin:0;max-width:none}.f{break-inside:avoid}}
"""
STATUS = {"explained": "Explained by the file", "stands": "Stands after investigation",
          "needs_human": "Needs a lawyer's review", "not_investigated": "Not yet investigated"}
CLIENT_STATUS = {"stands": "To be raised", "not_investigated": "To be raised",
                 "needs_human": "Under review by your lawyer"}
CAVEAT = ("The amount in question is the total of the individual discrepancies. It is not a calculation "
          "of loss or of what anyone owes. Some items may be explained once documents are produced.")


def money(x: Decimal) -> str:
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"


def write_json(items: list, path: Path) -> None:
    path.write_text(json.dumps([x.to_dict() for x in items], indent=2), encoding="utf-8")


def load_investigations(path: Path) -> list:
    from .agent import Investigation
    out = []
    for d in json.loads(path.read_text(encoding="utf-8")):
        d["citations"] = [Evidence(**c) for c in d.get("citations", [])]
        out.append(Investigation(**d))
    return out


def _page(title: str, body: list[str]) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)}</title>"
            f"<style>{CSS}</style></head><body>" + "\n".join(body) + "</body></html>")


def _category_table(t: dict, plain: bool) -> list[str]:
    rows = ["<table><tr><th>Category</th><th class='n'>Items</th><th class='n'>Amount</th></tr>"]
    for c in t["categories"]:
        amount = money(c["amount"]) if c["has_amount"] else "n/a"
        if c["has_amount"] and not c["counted"]:
            amount += " <span class='small'>(not added)</span>"
        rows.append(f"<tr><td>{escape(c['category'])}</td><td class='n'>{c['count']}</td><td class='n'>{amount}</td></tr>")
    label = "Total amount in question" if plain else "Amount in question (counted items only)"
    rows.append(f"<tr class='tot'><td>{label}</td><td class='n'>{t['open_count']}</td>"
                f"<td class='n'>{money(t['amount_in_question'])}</td></tr></table>")
    return rows


# --- lawyer's report --------------------------------------------------------------------------

def write_lawyer(m: Matter, findings: list[Finding], invs: list | None, path: Path, title: str) -> None:
    status = statuses(findings, invs)
    inv = {(i.type, i.key): i for i in invs or []}
    t = totals(findings, invs)
    by = t["by_status"]
    body = [
        "<div class='draft'>Draft work product. Verify every citation before relying on it.</div>",
        f"<h1>Reconciliation report: {escape(title)}</h1>",
        f"<p class='sub'>Prepared {date.today().isoformat()} &middot; {len(m.accounts)} accounts entries, "
        f"{len(m.bank)} bank transactions, {len(m.texts)} other documents reviewed</p>",
        "<div class='head'>"
        f"<div class='box'><b>{money(t['amount_in_question'])}</b><span>amount in question</span></div>"
        f"<div class='box'><b>{t['open_count']}</b><span>open items</span></div>"
        f"<div class='box'><b>{by['explained']['count']}</b><span>explained by the file"
        + (f" ({money(by['explained']['amount'])} set aside)" if by['explained']['count'] else "") + "</span></div></div>",
        f"<p class='note'>{CAVEAT} Each item is a discrepancy between documents, not a finding of fact or of wrongdoing."
        + ("" if t["investigated"] else " <b>The items have not been investigated yet</b>, so the total may "
           "include items that the file itself explains (a split payment, a reversed entry).") + "</p>",
        "<h2>Summary by category</h2>", *_category_table(t, plain=False),
    ]
    if t["investigated"]:
        body.append("<p class='small'>Of the amount in question, "
                    f"{money(by['stands']['amount'])} stands after investigation ({by['stands']['count']} items) and "
                    f"{money(by['needs_human']['amount'])} needs a lawyer's review ({by['needs_human']['count']} items).</p>")

    bridge = balance_bridge(m, findings)
    if bridge:
        number = {(f.type, f.key): n for n, f in enumerate(findings, start=1)}
        body += ["<h2>Balance bridge</h2>",
                 "<p class='small'>How the individual items add up to the gap between the balance the accounts "
                 "state and the balance at the bank. A residual of zero means the whole gap is traced to listed items.</p>",
                 "<table>",
                 f"<tr><td>Balance on hand stated in the accounts</td><td class='n'>{money(bridge['stated'])}</td></tr>"]
        for f, effect in bridge["lines"]:
            body.append(f"<tr><td>Item {number[(f.type, f.key)]}: {escape(info(f.type).label)}</td><td class='n'>{money(effect)}</td></tr>")
        if bridge["small_items"]:
            body.append(f"<tr><td>Small bank items not flagged (fees)</td><td class='n'>{money(-bridge['small_items'])}</td></tr>")
        body += [f"<tr><td>Unexplained residual</td><td class='n'>{money(bridge['residual'])}</td></tr>",
                 f"<tr class='tot'><td>Closing balance per bank record</td><td class='n'>{money(bridge['bank'])}</td></tr></table>"]

    def item(n: int, f: Finding) -> list[str]:
        amount = f"<span class='amt'>{money(f.amount)}</span>" if f.amount is not None else ""
        out = [f"<div class='f'><h3>{amount}<span class='tag {f.severity}'>{f.severity}</span>{n}. {escape(f.title)}</h3>"
               f"<div class='type'>{escape(info(f.type).label)}"
               + ("" if info(f.type).counted or f.amount is None else " &middot; amount not added to the total")
               + f"</div><p>{escape(f.detail)}</p>"]
        out += [f"<blockquote>{escape(e.quote)}<cite>{escape(e.doc)}, {escape(e.locator)}</cite></blockquote>" for e in f.evidence]
        i = inv.get((f.type, f.key))
        if i:
            out.append(f"<div class='inv {i.verdict}'><b>{STATUS[i.verdict]}</b><br>{escape(i.explanation or i.note)}"
                       + (f"<br><i>Override: {escape(i.note)}</i>" if i.note and i.explanation else ""))
            out += [f"<blockquote>{escape(e.quote)}<cite>{escape(e.doc)}, {escape(e.locator)}</cite></blockquote>" for e in i.citations]
            out.append("</div>")
        return out + ["</div>"]

    numbered = list(enumerate(findings, start=1))
    body.append("<h2>Open items</h2>")
    for n, f in numbered:
        if status[(f.type, f.key)] in OPEN:
            body += item(n, f)
    cleared = [(n, f) for n, f in numbered if status[(f.type, f.key)] == "explained"]
    if cleared:
        body.append("<h2>Explained by the file</h2><p class='small'>Left out of the total. Spot-check the cited lines.</p>")
        for n, f in cleared:
            body += item(n, f)
    body.append("<h2>Method and limits</h2><p class='small'>Matching, sums and date comparisons are done in code. "
                "Where an investigation ran, a language model looked for an innocent explanation in the file; an item is "
                "marked explained only on three agreeing passes, a second review and specific citations. The tool sees "
                "only the documents in the folder. Compensation is compared with a configurable rule of thumb, not with "
                "the law of any jurisdiction.</p>")
    path.write_text(_page(f"Reconciliation report: {title}", body), encoding="utf-8")


# --- client summary ---------------------------------------------------------------------------

def write_client(m: Matter, findings: list[Finding], invs: list | None, path: Path, title: str) -> None:
    status = statuses(findings, invs)
    t = totals(findings, invs)
    explained = t["by_status"]["explained"]["count"]
    body = [
        "<div class='draft'>Draft for your lawyer to review before it is sent to you</div>",
        f"<h1>Summary of our review: {escape(title)}</h1>",
        f"<p class='sub'>Prepared {date.today().isoformat()}</p>",
        "<h2>What we did</h2>",
        f"<p>We compared the executor's accounts ({len(m.accounts)} entries) with the bank statements "
        f"({len(m.bank)} transactions) and with {len(m.texts)} other documents, including the letters "
        "from the executor's lawyers. We looked for places where they do not agree.</p>",
        "<h2>What we found</h2>",
        "<div class='head'>"
        f"<div class='box'><b>{t['open_count']}</b><span>points to raise with the executor</span></div>"
        f"<div class='box'><b>{money(t['amount_in_question'])}</b><span>total amount in question</span></div>"
        + (f"<div class='box'><b>{explained}</b><span>points checked and explained</span></div>" if explained else "")
        + "</div>",
        *_category_table(t, plain=True),
        *([] if t["investigated"] else [
            "<p class='note'>This draft was produced before the points were checked for ordinary explanations "
            "in the documents themselves. Some may drop away once that is done.</p>"]),
        "<h2>What this does and does not mean</h2>",
        f"<p>{CAVEAT}</p><p>These are questions, not conclusions. A difference between two documents can have an "
        "ordinary explanation, and nothing here says that anyone acted improperly. The next step is for your "
        "lawyer to ask the executor for the documents and explanations listed in the request letter.</p>",
        "<h2>The points, one by one</h2>",
        "<table><tr><th>No.</th><th>What we found</th><th class='n'>Amount</th><th>Status</th></tr>",
    ]
    for n, f in enumerate(findings, start=1):
        s = status[(f.type, f.key)]
        if s not in OPEN:
            continue
        amount = "n/a" if f.amount is None else money(f.amount) + ("" if info(f.type).counted else "*")
        body.append(f"<tr><td>{n}</td><td>{escape(f.plain or f.title)}</td><td class='n'>{amount}</td>"
                    f"<td>{CLIENT_STATUS[s]}</td></tr>")
    body.append("</table><p class='small'>* Shown for information and not added to the total, because it overlaps "
                "with other points or no money is in doubt.</p>")
    if explained:
        body.append("<h2>Checked and explained</h2><p>These looked like differences at first, but the documents "
                    "themselves account for them. They are not included in the total.</p><ul>")
        body += [f"<li>{escape(f.plain or f.title)}</li>" for f in findings if status[(f.type, f.key)] == "explained"]
        body.append("</ul>")
    path.write_text(_page(f"Summary of our review: {title}", body), encoding="utf-8")


# --- schedule and bundle ----------------------------------------------------------------------

def write_schedule(findings: list[Finding], invs: list | None, path: Path) -> None:
    status = statuses(findings, invs)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "category", "type", "severity", "status", "amount", "added_to_total", "description", "sources"])
        for n, f in enumerate(findings, start=1):
            s = status[(f.type, f.key)]
            added = info(f.type).counted and f.amount is not None and s in OPEN
            w.writerow([n, info(f.type).category, f.type, f.severity, s,
                        "" if f.amount is None else f"{f.amount:.2f}", "yes" if added else "no", f.title,
                        "; ".join(f"{e.doc}, {e.locator}" for e in f.evidence)])


def write_all(m: Matter, findings: list[Finding], invs: list | None, out: Path, title: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    write_json(findings, out / "findings.json")
    write_lawyer(m, findings, invs, out / "report_lawyer.html", title)
    write_client(m, findings, invs, out / "report_client.html", title)
    write_schedule(findings, invs, out / "schedule.csv")
    (out / "draft_request_letter.md").write_text(draft_request(findings, invs or []), encoding="utf-8")
    return [out / n for n in ("report_lawyer.html", "report_client.html", "schedule.csv", "draft_request_letter.md")]
