"""Write findings as JSON (for machines) and a self-contained HTML memo (for people)."""
from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path

from .models import Finding, Matter

CSS = """
body{font:15px/1.5 Georgia,serif;max-width:860px;margin:40px auto;padding:0 20px;color:#1c1c1c}
h1{font-size:24px;margin-bottom:4px} .sub{color:#555;margin-top:0}
.note{background:#f6f4ee;border-left:3px solid #8a7a4a;padding:10px 14px;font-size:14px}
.f{border:1px solid #ddd;border-radius:6px;padding:14px 18px;margin:16px 0}
.f h2{font-size:17px;margin:0 0 6px} .tag{font:11px/1 Arial,sans-serif;text-transform:uppercase;
letter-spacing:.06em;padding:3px 7px;border-radius:3px;color:#fff;margin-right:8px;vertical-align:2px}
.high{background:#9b2c2c}.medium{background:#b7791f}.low{background:#4a5568}
.type{font:12px Arial,sans-serif;color:#666}
blockquote{margin:8px 0 0;padding:6px 12px;border-left:3px solid #ccc;font-size:14px;background:#fafafa}
cite{display:block;font:12px Arial,sans-serif;color:#666;font-style:normal}
.inv{margin-top:14px;padding:10px 14px;border-radius:4px;font-size:14px}
.inv b{font:12px Arial,sans-serif;text-transform:uppercase;letter-spacing:.05em}
.explained{background:#edf7ed}.stands{background:#fdeeee}.needs_human{background:#fdf6e3}
.f.cleared{opacity:.6}
"""
VERDICT_LABEL = {"explained": "Explained by the file", "stands": "Stands after investigation",
                 "needs_human": "Needs a lawyer's review"}


def write_json(items: list, path: Path) -> None:
    path.write_text(json.dumps([x.to_dict() for x in items], indent=2), encoding="utf-8")


def write_html(m: Matter, findings: list[Finding], path: Path, investigations: list | None = None) -> None:
    inv = {(i.type, i.key): i for i in investigations or []}
    counts = Counter(f.severity for f in findings)
    verdicts = Counter(i.verdict for i in inv.values())
    parts = [
        f"<!doctype html><html><head><meta charset='utf-8'><title>Reconciliation memo</title><style>{CSS}</style></head><body>",
        "<h1>Reconciliation memo</h1>",
        f"<p class='sub'>Matter folder: {escape(m.root)} &middot; {len(m.accounts)} accounts entries, "
        f"{len(m.bank)} bank transactions, {len(m.texts)} narrative documents &middot; "
        f"{len(findings)} findings ({counts['high']} high, {counts['medium']} medium, {counts['low']} low)"
        + (f" &middot; after investigation: {verdicts['stands']} stand, {verdicts['needs_human']} need review, "
           f"{verdicts['explained']} explained" if inv else "") + "</p>",
        "<p class='note'>Each item below is a discrepancy between documents, with the passages relied on. "
        "It is a list of questions to put to the other side, not a finding of fact or of wrongdoing. "
        "Verify every citation against the source before relying on it.</p>",
    ]
    for n, f in enumerate(findings, start=1):
        i = inv.get((f.type, f.key))
        cleared = " cleared" if i and i.verdict == "explained" else ""
        parts.append(f"<div class='f{cleared}'><h2><span class='tag {f.severity}'>{f.severity}</span>"
                     f"{n}. {escape(f.title)}</h2><div class='type'>{escape(f.type)}</div>"
                     f"<p>{escape(f.detail)}</p>")
        for ev in f.evidence:
            parts.append(f"<blockquote>{escape(ev.quote)}<cite>{escape(ev.doc)}, {escape(ev.locator)}</cite></blockquote>")
        if i:
            parts.append(f"<div class='inv {i.verdict}'><b>{VERDICT_LABEL[i.verdict]}</b><br>"
                         f"{escape(i.explanation or i.note)}"
                         + (f"<br><i>Override: {escape(i.note)}</i>" if i.note and i.explanation else ""))
            for ev in i.citations:
                parts.append(f"<blockquote>{escape(ev.quote)}<cite>{escape(ev.doc)}, {escape(ev.locator)}</cite></blockquote>")
            parts.append("</div>")
        parts.append("</div>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")
