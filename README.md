# Estate Reconciler

Cross-checks an executor's statement of accounts against the bank record and the
correspondence, investigates each discrepancy, and produces a memo and a draft
document-request letter in which every item cites the document and line it rests on.

It works in two stages.

**Stage 1, the checks (plain code).** Raises every discrepancy it can see:

- accounts entries with no bank transaction behind them, and the reverse
- amount and date differences between the two
- totals that do not add up; a stated balance that does not match the bank
- documents a letter says are enclosed or coming that are not in the file
- a letter describing a document as outstanding after the date on the document
- figures quoted in letters that do not match the records
- compensation above a configurable starting point

**Stage 2, the investigator (an agent).** For each finding, a model with read-only tools
looks for an innocent explanation already in the file: a split payment, a reversed entry,
a document filed under another name. It returns `explained`, `stands` or `needs_human`,
with citations. Findings that are not explained go into a draft request letter for a
lawyer to review. Nothing is sent.

## Run it

Python 3.10+, no dependencies.

```
python make_demo.py                                   # writes the fictional demo matter
python -m reconciler analyze demo_matter --out out    # stage 1: findings.json + memo.html
python -m reconciler ask demo_matter "Were the T3 returns ever provided?"
python evals/run_eval.py                              # stage 1 scores
python -m unittest discover tests
```

Stage 2 and model-written answers for `ask` need an OpenAI-compatible endpoint. A local
one keeps privileged documents on your own machine. The model must support tool calling.

```
export RECONCILER_LLM_BASE_URL=http://localhost:11434/v1     # e.g. Ollama
export RECONCILER_LLM_MODEL=<a tool-calling model you have pulled>

python -m reconciler investigate demo_matter --out out   # memo with verdicts + draft letter
python evals/run_agent_eval.py                           # stage 2 scores
```

## Design choices

**Arithmetic is never delegated to a model.** Matching, sums and date comparisons are
plain code (`checks.py`). The agent has an `add_amounts` tool for the same reason.

**The model decides where to look; code decides what it may conclude** (`agent.py`):

- `explained` must cite at least one passage that was not already in the finding.
- Every citation must be a reference a tool actually returned in that investigation.
  An invented source turns the verdict into `needs_human`.
- No verdict within the step limit, a model error, or an unrecognised verdict: `needs_human`.
- Questions of judgment (is the compensation reasonable?) go to a lawyer without asking
  the model at all.
- An arithmetic error or a balance gap can never be marked `explained`. The model's
  account is kept as a lead for the reviewer.

**The errors are not symmetric.** Sending an explained item to a lawyer costs minutes.
Clearing a real one loses it. Every fallback lands on `needs_human`.

**Every step is auditable.** Each investigation records every tool call and result
(`investigations.json`), so a reviewer can see what the agent looked at, not only what
it concluded.

**The letter is a template, not generated prose.** A draft built from fixed wording
cannot introduce a fact that is not in the findings.

**Findings are questions, not accusations.** The memo describes what two documents say
and where they differ. It does not characterise anyone's conduct.

## How it is tested

The demo matter contains eleven real problems and five decoys, all labelled in
`evals/ground_truth.json`. A decoy looks like a problem to stage 1 and is explained
elsewhere in the file.

Stage 1, the checks (plain code, no model):

| Measure | Result |
|---|---|
| Raises all 16 labelled items, nothing else | 16 of 16, 0 unexpected |
| Share of raised items that are real problems | 69% (11 of 16), by design |
| Control file with no problems | 0 findings |

Stage 2, the investigator, on the same 16 findings (local models, 2026-11-16):

| Model | Agent version | Real problems wrongly dismissed | Decoys cleared | Sent to a lawyer | Real share of what remains |
|---|---|---|---|---|---|
| `qwen3.8:27b` (dense) | v1: 8 steps, no stated budget | 0 of 11 | 5 of 5 | 5 (1 by rule, 1 by the model, 3 at the step limit) | 100% (11 of 11) |
| `qwen3.8:27b` (dense) | v2: 10 steps, budget stated, last-step warning | 0 of 11 | 5 of 5 | 2 (1 by rule, 1 by the model) | 100% (11 of 11) |
| `qwen3.6:35b` (MoE) | v2 | **2 of 11** | 2 of 5 | 1 (by rule) | 75% (9 of 12) |

One run per row. The v1 and v2 rows for the dense model differ in the agent, not in luck:
v1 ran out of steps on three findings where the right answer was "nothing explains this",
and v2 fixed that.

The MoE row is the most useful result here. That model marked the $5,000 total error and
the balance gap as "explained", the planted trap described below, despite a prompt rule
written to prevent exactly that. Its citations were real, so the citation guardrails let
the verdict through. The response was a rule in code, not a firmer prompt: those two
kinds of finding can no longer be cleared by any model (agent v3). Results for v3 are
not yet measured.

The stage 2 tests in `tests/test_agent.py` use a scripted stand-in for the model. They
prove the loop, tools and guardrails behave, and that each decoy's explanation is
reachable with the tools provided. They say nothing about how well a real model
investigates. That is what `run_agent_eval.py` measures. One run on one small file is a
first reading, not a benchmark.

One planted trap to watch: the summary overstates disbursements by exactly $5,000, the
same size as an e-transfer missing from the accounts. A model may call one an
explanation of the other. It is a link between two problems, not an explanation of either.

## What the evals have caught so far

- Stage 1's first run scored 82%. A CRA Notice of Assessment whose title mentions "T3"
  was classified as a T3 return, hiding two findings at once. Fixed in `extract.classify_doc`.
- A test stand-in that tried to dismiss a real problem by citing the finding's own
  evidence was overridden by the new-evidence rule. The test had to be rewritten to get
  a wrong dismissal past it.

- Stage 2's first run hit the step limit on three real findings. Each was a case where the
  right answer is "nothing explains this", and the model kept searching instead of
  concluding. The agent is now told its budget up front and warned before its last step.
- A second local model cleared two real problems by citing a third of the same size.
  A prompt rule did not stop it; a code rule now does. The wider weakness remains: for
  other kinds of finding, a model can still present a related problem as an explanation.

## Limits

- Stage 1's scores are on a file whose problems and checks were written together. They
  show the pipeline works end to end, not how it performs on real productions.
- Stage 2 has single runs on two models, and the results differ sharply by model. Which
  model is used is a safety decision, not a detail. The decoys were written to be findable with the tools
  provided; real explanations will be harder to find.
- Input is clean CSV and text. Real bank statements arrive as scanned PDFs; OCR and table
  extraction are the hard part and are not here.
- Letter analysis in stage 1 is pattern-based. It misses paraphrase and is confused by
  abbreviations that end in a full stop.
- One bank account, one currency.
- The compensation guideline is a configurable rule of thumb, not a statement of the law
  in any jurisdiction.

## Roadmap

1. Run stage 2 on two or three local models; record the scores and each prompt revision.
2. A second matter written by someone else, as a held-out test.
3. An LLM extractor behind `extract.statements()`, scored against the rule-based baseline.
4. PDF and scanned-statement ingestion.

## Disclosure

All names, firms, addresses and figures in the demo matter are invented. The code was
written with substantial assistance from Claude (Anthropic); the problem definition,
the checks chosen and the review of the output are mine.
