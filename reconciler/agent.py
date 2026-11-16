"""The investigator: for one finding, look for an innocent explanation in the file.

The model decides where to look. Code decides what it is allowed to conclude:

  * a verdict of "explained" must cite at least one passage that was not already in the finding;
  * every citation must be a ref a tool actually returned during this investigation;
  * no verdict within the step limit, or any model error, becomes "needs_human";
  * findings that turn on legal judgment are routed to a person without asking the model;
  * an arithmetic error or balance gap can never be marked "explained".

The errors are not symmetric. Sending an explained item to a lawyer costs a few minutes;
clearing a real one loses it. Every fallback therefore lands on "needs_human".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from .models import Evidence, Finding, Matter
from .tools import SPECS, Toolbox

VERDICTS = {"explained", "stands", "needs_human"}
JUDGMENT_ONLY = {"compensation_review"}   # reasonableness is a legal question, not a lookup
# Findings the file cannot explain away. A total that does not equal the sum of its entries is
# wrong whatever else is in the file; the model may identify a likely cause, but that is a lead,
# not a clearance. A balance gap can have an innocent cause (an uncashed cheque), but a
# reconciliation is for a person to verify. Added after a model cleared both by pointing at
# another problem of the same size.
NOT_CLEARABLE = {"arithmetic_error": "stands", "balance_mismatch": "needs_human"}

SYSTEM = """You assist a lawyer acting for a beneficiary of an estate. A first-pass check has \
flagged a discrepancy between the executor's accounts, the bank record and the correspondence. \
Before the lawyer raises it with the other side, test whether the file already explains it.

Method:
1. Work out what would have to be true for the discrepancy to be innocent: a payment split \
across several transactions, an entry later reversed, a document that is in the file under a \
different name, or a timing difference.
2. Use the tools to look in the places where that explanation would be.
3. Call submit_verdict.

Verdicts:
- explained: specific passages or transactions in the file account for the WHOLE discrepancy. \
Amounts must reconcile exactly (use add_amounts). Cite the passages that explain it.
- stands: you looked where an explanation would be and found none.
- needs_human: the explanation is partial or ambiguous, or the question is one of judgment.

Rules:
- Clearing a real problem is the worst mistake you can make. If in doubt, do not choose explained.
- Finding a second problem of the same size is not an explanation. It is a link; report it and \
choose stands or needs_human.
- Cite only refs returned by the tools, copied exactly.
- Describe what the documents show. Do not speculate about anyone's motives."""


BUDGET = ("You have {n} steps. A tool call is one step. Two or three well-aimed searches that "
          "find nothing are enough to conclude 'stands'; do not keep rephrasing the same search.")
LAST_STEP = ("This is your last step. Call submit_verdict now. If you looked where an explanation "
             "would be and found none, the verdict is 'stands'. If you found something partial, "
             "'needs_human'.")


@dataclass
class Investigation:
    type: str
    key: str
    verdict: str
    explanation: str
    citations: list[Evidence] = field(default_factory=list)
    rejected_citations: list[str] = field(default_factory=list)
    note: str = ""                       # set when code overrode or supplied the verdict
    trace: list[dict] = field(default_factory=list)   # every tool call, for audit

    def to_dict(self) -> dict:
        return asdict(self)


def _args(call: dict) -> dict:
    raw = call.get("function", {}).get("arguments", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _finalize(f: Finding, box: Toolbox, args: dict, trace: list[dict]) -> Investigation:
    verdict = args.get("verdict")
    cited = [c for c in args.get("citations") or [] if isinstance(c, str)]
    valid = [c for c in cited if c in box.seen]
    rejected = [c for c in cited if c not in box.seen]
    note = ""
    if verdict not in VERDICTS:
        verdict, note = "needs_human", "model returned an unrecognised verdict"
    elif verdict == "explained" and rejected:
        verdict, note = "needs_human", "model cited a source that no tool returned"
    elif verdict == "explained" and f.type in NOT_CLEARABLE:
        verdict = NOT_CLEARABLE[f.type]
        note = "model said 'explained'; this kind of finding cannot be cleared by the file, so its account is kept as a lead only"
    elif verdict == "explained" and not any(c not in box.original for c in valid):
        verdict, note = "needs_human", "model said 'explained' without citing any new evidence"
    evidence = [Evidence(*c.split(" :: ", 1), box.seen[c]) for c in valid]
    return Investigation(f.type, f.key, verdict, str(args.get("explanation", "")),
                         evidence, rejected, note, trace)


def investigate(f: Finding, matter: Matter, client, max_steps: int = 10) -> Investigation:
    """`client` is anything with complete(messages, tools) -> assistant message dict."""
    if f.type in JUDGMENT_ONLY:
        return Investigation(f.type, f.key, "needs_human", "",
                             note="routed to a lawyer by rule: this turns on judgment, not on the documents")

    def bail(note: str) -> Investigation:
        return Investigation(f.type, f.key, "needs_human", "", note=note, trace=trace)

    box = Toolbox(matter, f)
    trace: list[dict] = []
    brief = {"type": f.type, "title": f.title, "detail": f.detail,
             "evidence": [{"ref": f"{e.doc} :: {e.locator}", "text": e.quote} for e in f.evidence]}
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Finding to investigate:\n" + json.dumps(brief, indent=2)
                 + "\n\n" + BUDGET.format(n=max_steps)}]
    nudged = False

    for step in range(max_steps):
        if step == max_steps - 1 and max_steps > 1:
            # Proving a negative has no natural stopping point, so the model is told when to stop.
            messages.append({"role": "user", "content": LAST_STEP})
        try:
            msg = client.complete(messages, SPECS)
        except Exception as e:  # network, bad JSON, model without tool support
            return bail(f"model error: {e}")
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls}
                        if calls else {"role": "assistant", "content": msg.get("content") or ""})
        if not calls:
            if nudged:
                return bail("model did not submit a verdict")
            nudged = True
            messages.append({"role": "user", "content": "Use a tool, or call submit_verdict to finish."})
            continue
        for call in calls:
            name, args = call.get("function", {}).get("name", ""), _args(call)
            if name == "submit_verdict":
                return _finalize(f, box, args, trace)
            result = box.call(name, args)
            trace.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": json.dumps(result)})
    return bail("step limit reached without a verdict")


def investigate_all(findings: list[Finding], matter: Matter, client, max_steps: int = 10,
                    progress=None) -> list[Investigation]:
    out = []
    for f in findings:
        inv = investigate(f, matter, client, max_steps)
        if progress:
            progress(f, inv)
        out.append(inv)
    return out
