"""Ask questions of the matter. BM25 retrieval over every line, ledger row and finding,
with an optional language model that may only answer from the retrieved passages."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from . import llm
from .models import Finding, Matter


@dataclass
class Chunk:
    doc: str
    locator: str
    text: str


def _tok(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def build_chunks(m: Matter, findings: list[Finding]) -> list[Chunk]:
    chunks = [Chunk(t.doc, t.locator, f"{t.date} {t.description} ${t.amount:,.2f} "
                    f"({'receipt' if t.direction == 'in' else 'disbursement'})")
              for t in m.accounts + m.bank]
    for key, (_, ev) in m.summary.items():
        chunks.append(Chunk(ev.doc, ev.locator, ev.quote))
    for d in m.texts:
        chunks += [Chunk(d.name, f"line {i}", ln.strip())
                   for i, ln in enumerate(d.lines, start=1) if ln.strip()]
    for f in findings:
        chunks.append(Chunk("findings", f"{f.type}:{f.key}", f"{f.title}. {f.detail}"))
    return chunks


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.tf = [Counter(_tok(c.text)) for c in chunks]
        self.len = [sum(tf.values()) for tf in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        df = Counter(term for tf in self.tf for term in tf)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 6) -> list[Chunk]:
        q = _tok(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                scores.append((s, i))
        return [self.chunks[i] for _, i in sorted(scores, reverse=True)[:k]]


SYSTEM = (
    "You answer questions about an estate file for a lawyer. Use ONLY the numbered passages. "
    "Cite every factual sentence with its passage number in square brackets, e.g. [2]. "
    "If the passages do not answer the question, say so. Do not characterise anyone's conduct "
    "or give a legal conclusion; describe what the documents show.")


def ask(m: Matter, findings: list[Finding], question: str, k: int = 6) -> dict:
    hits = BM25(build_chunks(m, findings)).search(question, k)
    passages = "\n".join(f"[{i}] ({c.doc}, {c.locator}) {c.text}" for i, c in enumerate(hits, start=1))
    answer = None
    if llm.configured() and hits:
        answer = llm.chat(SYSTEM, f"Passages:\n{passages}\n\nQuestion: {question}")
    return {"question": question, "answer": answer, "passages": hits}
