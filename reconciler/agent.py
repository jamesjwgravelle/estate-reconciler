"""The investigator: for one finding, look for an innocent explanation in the file.

The model decides where to look. Code decides what it is allowed to conclude:

  * a verdict of "explained" must cite at least one passage that was not already in the finding;
  * every citation must be a ref a tool actually returned during this investigation;
  * no verdict within the step limit, or any model error, becomes "needs_human";
  * findings that turn on legal judgment are routed to a person without asking the model;
  * an arithmetic error or balance gap can never be marked "explained";
  * clearing takes three agreeing runs and a second reviewer; keeping takes one run.

The errors are not symmetric. Sending an explained item to a lawyer costs a few minutes;
clearing a real one loses it. Every fallback therefore lands on "needs_human".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from .models import Evidence, Finding, Matter
from .tools import SPECS, Toolbox, ref

AGENT_VERSION = "v7"   # bump whenever the prompt or a rule changes, so eval runs stay comparable

VERDICTS = {"explained", "stands", "needs_human"}
# Questions of judgment, not lookup: is the compensation reasonable; who should bear a penalty.
JUDGMENT_ONLY = {"compensation_review", "avoidable_cost", "personal_legal_fees", "agent_fee_offset"}
# Findings the file cannot explain away. A total that does not equal the sum of its entries is
# wrong whatever else is in the file; the model may identify a likely cause, but that is a lead,
# not a clearance. A balance gap can have an innocent cause (an uncashed cheque), but a
# reconciliation is for a person to verify. Added after a model cleared both by pointing at
# another problem of the same size.
NOT_CLEARABLE = {"arithmetic_error": "stands", "invoice_arithmetic": "stands", "balance_mismatch": "needs_human"}

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

REVIEW_SYSTEM = """You are the second reviewer of a proposed clearance. Another reviewer says a \
discrepancy in an estate file is innocently explained by the cited evidence. You see only the \
discrepancy, the proposed explanation and the cited evidence. Decide whether that evidence, on \
its own, fully accounts for the discrepancy.

Reject if any of these is true:
- the evidence accounts for only part of the amount, or the amounts do not reconcile exactly;
- the evidence is a different document, year, payee or property from the one in question;
- a cited item is itself flagged as a problem and would STILL be a problem if the explanation \
were accepted. Two halves of one payment, or a transaction and its reversal, resolve each \
other and are acceptable. A missing transfer that happens to equal an error elsewhere is not;
- you would need to assume a fact that the evidence does not state.

If in doubt, reject. A rejection only sends the item to a lawyer."""

REVIEW_SPEC = [{"type": "function", "function": {
    "name": "submit_review",
    "description": "Give your decision on the proposed clearance.",
    "parameters": {"type": "object", "required": ["decision", "reason"], "properties": {
        "decision": {"type": "string", "enum": ["confirm", "reject"]},
        "reason": {"type": "string", "description": "One or two sentences"}}}}}]


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
    checks: dict = field(default_factory=dict)        # repeat runs and second review, if any

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


def investigate(f: Finding, matter: Matter, client, max_steps: int = 10, sample: int = 0) -> Investigation:
    """One investigation. `client` is anything with complete(messages, tools, **opts) -> message.
    sample 0 is the deterministic run; higher samples use some temperature and a fixed seed,
    so that repeat runs are a real second opinion and not a replay."""
    if f.type in JUDGMENT_ONLY:
        return Investigation(f.type, f.key, "needs_human", "",
                             note="routed to a lawyer by rule: this turns on judgment, not on the documents")

    def bail(note: str) -> Investigation:
        return Investigation(f.type, f.key, "needs_human", "", note=note, trace=trace)

    opts = {"temperature": 0.5, "seed": sample} if sample else {}
    box = Toolbox(matter, f)
    trace: list[dict] = []
    brief = {"type": f.type, "title": f.title, "detail": f.detail,
             "evidence": [{"ref": ref(e.doc, e.locator), "text": e.quote} for e in f.evidence]}
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Finding to investigate:\n" + json.dumps(brief, indent=2)
                 + "\n\n" + BUDGET.format(n=max_steps)}]
    nudged = False

    for step in range(max_steps):
        if step == max_steps - 1 and max_steps > 1:
            # Proving a negative has no natural stopping point, so the model is told when to stop.
            messages.append({"role": "user", "content": LAST_STEP})
        try:
            msg = client.complete(messages, SPECS, **opts)
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


def review_clearance(f: Finding, inv: Investigation, flagged: dict[str, list[str]], client) -> tuple[bool, str]:
    """Second key. A fresh call that sees only the finding, the claim and the cited evidence.
    `flagged` maps a ref to the titles of OTHER findings that rely on it: a fact computed in
    code, handed to the reviewer so it does not have to guess whether a citation is itself
    in dispute."""
    packet = {
        "discrepancy": {"title": f.title, "detail": f.detail,
                        "evidence": [{"ref": ref(e.doc, e.locator), "text": e.quote} for e in f.evidence]},
        "proposed_explanation": inv.explanation,
        "cited_evidence": [{"ref": ref(e.doc, e.locator), "text": e.quote,
                            "also_flagged_as": flagged.get(ref(e.doc, e.locator), [])}
                           for e in inv.citations],
    }
    try:
        msg = client.complete([{"role": "system", "content": REVIEW_SYSTEM},
                               {"role": "user", "content": json.dumps(packet, indent=2)}], REVIEW_SPEC)
    except Exception as e:
        return False, f"reviewer error: {e}"
    for call in msg.get("tool_calls") or []:
        if call.get("function", {}).get("name") == "submit_review":
            args = _args(call)
            if args.get("decision") in ("confirm", "reject"):
                return args["decision"] == "confirm", str(args.get("reason", ""))
    return False, "reviewer gave no usable answer"


def investigate_checked(f: Finding, matter: Matter, client, all_findings: list[Finding],
                        runs: int = 3, verify: bool = True, max_steps: int = 10, reviewer=None) -> Investigation:
    """Investigate, and make "explained" earn its place.

    A first run that keeps the finding is accepted as is: that is the safe direction. A first
    run that clears it must be matched by every repeat run and then confirmed by the second
    reviewer. On any disagreement the finding goes to a lawyer, with the first run's account
    kept as a lead."""
    inv = investigate(f, matter, client, max_steps)
    if inv.verdict != "explained":
        return inv

    verdicts = ["explained"]
    for sample in range(1, runs):
        verdicts.append(investigate(f, matter, client, max_steps, sample=sample).verdict)
        if verdicts[-1] != "explained":
            break
    inv.checks["runs"] = verdicts
    if set(verdicts) != {"explained"}:
        inv.verdict, inv.note = "needs_human", f"repeat runs disagreed ({', '.join(verdicts)})"
        return inv

    if verify:
        flagged: dict[str, list[str]] = {}
        for other in all_findings:
            if (other.type, other.key) != (f.type, f.key):
                for e in other.evidence:
                    flagged.setdefault(ref(e.doc, e.locator), []).append(other.title)
        # A different model as reviewer is a more independent check than a model marking its own work.
        ok, reason = review_clearance(f, inv, flagged, reviewer or client)
        inv.checks["review"] = {"confirmed": ok, "reason": reason}
        if not ok:
            inv.verdict, inv.note = "needs_human", f"second reviewer did not confirm: {reason}"
    return inv


def investigate_all(findings: list[Finding], matter: Matter, client, runs: int = 3, verify: bool = True,
                    max_steps: int = 10, progress=None, reviewer=None) -> list[Investigation]:
    out = []
    for f in findings:
        inv = investigate_checked(f, matter, client, findings, runs, verify, max_steps, reviewer)
        if progress:
            progress(f, inv)
        out.append(inv)
    return out
