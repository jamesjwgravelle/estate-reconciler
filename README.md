# Estate Reconciler

Cross-checks an executor's statement of accounts against the bank record and the
correspondence, investigates each discrepancy, and produces a lawyer's report, a client
summary and a draft document-request letter. Every item cites the document and line it
rests on, and the reports put a dollar figure on what is in question.

It works in two stages.

**Stage 1, the checks (plain code).** Raises every discrepancy it can see:

- accounts entries with no bank transaction behind them, and the reverse
- amount and date differences between the two
- totals that do not add up; a stated balance that does not match the bank
- documents a letter says are enclosed or coming that are not in the file
- a letter describing a document as outstanding after the date on the document
- figures quoted in letters that do not match the records
- compensation above a configurable starting point
- gifts of money in the will with no payment in the accounts
- penalties and late charges paid out of the estate
- a lawyer's invoice whose time entries do not add up to the fees billed
- the same time entry billed twice
- time that looks like advice to the executor personally, billed to the estate
- a letter saying a document has not arrived when the firm's own time records show work on it
- a form dated months before it was signed, and a long gap between the final tax assessment
  and the application for the clearance certificate
- a paid agent (such as a trust company) administering the estate alongside full executor
  compensation
- a tax payment on a reassessment with no matching notice in the file

**Stage 2, the investigator (an agent).** For each finding, a model with read-only tools
looks for an innocent explanation already in the file: a split payment, a reversed entry,
a document filed under another name. It returns `explained`, `stands` or `needs_human`,
with citations. Findings that are not explained go into a draft request letter for a
lawyer to review. Nothing is sent.

## Run it

Python 3.10+, no dependencies.

```
python make_demo.py                                   # writes the fictional demo matter
python -m reconciler analyze demo_matter --out out    # stage 1: checks, then the reports
python verify.py                                      # tests + stage 1 eval + reports, one command
python -m reconciler ask demo_matter "Were the T3 returns ever provided?"
python evals/run_eval.py                              # stage 1 scores
python -m unittest discover tests
```

Stage 2 and model-written answers for `ask` need an OpenAI-compatible endpoint. A local
one keeps privileged documents on your own machine. The model must support tool calling.

```
export RECONCILER_LLM_BASE_URL=http://localhost:11434/v1     # e.g. Ollama
export RECONCILER_LLM_MODEL=<a tool-calling model you have pulled>

python -m reconciler investigate demo_matter --out out   # reports with verdicts + draft letter
python -m reconciler report demo_matter --out out        # rebuild the reports without re-running the model
python evals/run_agent_eval.py                           # stage 2 scores, saved to evals/runs/
python evals/run_agent_eval.py --runs 1 --no-verify      # the bare agent, for comparison
export RECONCILER_REVIEW_MODEL=<a different model>       # optional: independent second reviewer
python evals/make_table.py --write                       # rebuild the results table below
```

A lawyer-facing explanation of the output is in [GUIDE.md](GUIDE.md).

## What it produces

| File | For | Contents |
|---|---|---|
| `report_lawyer.html` | the lawyer | dollar total, table by category, balance bridge, every item with its citations and verdict |
| `report_client.html` | the client, after the lawyer has reviewed it | the same items and numbering in plain language, no citations |
| `schedule.csv` | working papers | one row per item: category, status, amount, whether it is in the total, sources |
| `draft_request_letter.md` | the lawyer | a request for each open item, from fixed wording |
| `findings.json`, `investigations.json` | audit | everything above in machine-readable form, including each tool call the agent made |

**The dollar figure.** The "amount in question" adds up the open discrepancies. Two rules
keep it defensible. Nothing is counted twice: a wrong total and a balance gap are symptoms
of the items behind them, so they are shown but not added. And anything the investigator
found to be explained by the file is left out. It is not a damages figure, and both
reports say so.

**The balance bridge.** The lawyer's report shows, in code-computed arithmetic, how the
individual items add up to the gap between the stated balance and the bank balance. On
the demo matter the unexplained residual is $0.00. A residual that is not zero means
something moved the balance that no check has identified.

## Extending it

Each check is one file in `reconciler/rules/`. Adding one does not mean editing any
existing check. `AGENTS.md` has the recipe, the rules that must not be broken, and a
backlog of small, self-contained tasks. It is written so that a coding assistant, including
a small local model, can take one task at a time; `python verify.py` tells it whether the
change is safe.

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
- Clearing takes more than keeping. If a first run keeps a finding, that is accepted. If
  it clears one, two further runs (sampled, fixed seeds) must agree, and then a second
  reviewer must confirm. The reviewer is a fresh call that sees only the finding, the
  claim and the cited evidence, and is told by code which citations are themselves
  relied on by another finding. Any dissent sends the item to a lawyer. Set
  `RECONCILER_REVIEW_MODEL` to have a different model act as reviewer, so that no model
  marks its own work.

**The errors are not symmetric.** Sending an explained item to a lawyer costs minutes.
Clearing a real one loses it. Every fallback lands on `needs_human`.

**Every step is auditable.** Each investigation records every tool call and result
(`investigations.json`), so a reviewer can see what the agent looked at, not only what
it concluded.

**The reports are built by code.** Totals, categories and the bridge come from `summary.py`;
no model writes or sums anything in them.

**The letter is a template, not generated prose.** A draft built from fixed wording
cannot introduce a fact that is not in the findings.

**Findings are questions, not accusations.** The report describes what two documents say
and where they differ. It does not characterise anyone's conduct.

## How it is tested

The demo matter contains real problems and decoys (counts in the table below), all labelled in
`evals/ground_truth.json`. A decoy looks like a problem to stage 1 and is explained
elsewhere in the file.

Stage 1, the checks (plain code, no model). Generated by `python evals/make_table.py --write`:

<!-- stage1:start -->
| Measure | Result |
|---|---|
| Labelled items in the demo matter (dataset 4) | 21 real problems, 6 decoys |
| Raises every labelled item, nothing else | 27 of 27, 0 unexpected |
| Share of raised items that are real problems | 78% (21 of 27), by design |
| Control file with no problems (17 documents besides the ledgers) | 0 findings |
<!-- stage1:end -->

Stage 2, early runs on the first version of the demo (11 real problems, 5 decoys; local models, 2026-11-16; recorded by hand, before runs were saved to file):

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
kinds of finding can no longer be cleared by any model (agent v3). Agent v4 then made
every clearance need three agreeing runs and a second reviewer.

Stage 2, current agent. This table is also generated from the files in `evals/runs/` by
`python evals/make_table.py --write`; nothing in it is typed by hand.

<!-- results:start -->
| Model | Agent configuration | Eval runs | Real problems wrongly dismissed (worst run) | Decoys cleared | Sent to a lawyer | of which model errors |
|---|---|---|---|---|---|---|
| `qwen3.8` | v6, demo set 3, 1 run(s) to clear, no second reviewer | 1 | 0 of 17 | 6 of 6 | 4 | 0 |
| `qwen3.8` | v6, demo set 3, 3 run(s) to clear, second reviewer `qwen3.6:35b` | 1 | 0 of 17 | 4 of 6 | 6 | 0 |
| `qwen3.8:27b-q8_0` | v7, demo set 4, 1 run(s) to clear, no second reviewer | 1 | 0 of 21 | 5 of 6 | 10 | 0 |
| `qwen3.8:27b-q8_0` | v7, demo set 4, 3 run(s) to clear, second reviewer | 3 | 0 of 21 | 4 to 5 of 6 | 6 to 11 | 0 |
| `qwen3.8:27b-q8_0` | v7, demo set 4, 3 run(s) to clear, second reviewer `gemma4:31b` | 3 | 0 of 21 | 6 of 6 | 4 to 6 | 0 |
<!-- results:end -->

Note: one `gemma4:31b` run (2026-11-18 13:27) predates error counting; two of its six
items sent to a lawyer were timeouts, not model judgments.

The stage 2 tests in `tests/test_agent.py` use a scripted stand-in for the model. They
prove the loop, tools and guardrails behave, and that each decoy's explanation is
reachable with the tools provided. They say nothing about how well a real model
investigates. That is what `run_agent_eval.py` measures. One run on one small file is a
first reading, not a benchmark.

The file also contains eight routine letters with nothing wrong in them, so that not
every document is a problem. Three planted traps test whether a model mistakes something
related for an explanation: a letter saying the roof repairs were completed (not evidence
that the estate paid for them), a $150,000 distribution to beneficiaries (not the $10,000
gift to the library), and the one below.

One planted trap to watch: the summary overstates disbursements by exactly $5,000, the
same size as an e-transfer missing from the accounts. A model may call one an
explanation of the other. It is a link between two problems, not an explanation of either.

**Reprints are not issue dates.** A reprinted notice can carry its reprint date above its
issue date. Read naively, a notice issued in December and reprinted in July looks as if it
arrived in July, and the letters that called it outstanding in between look accurate.
`ingest.py` skips reprint lines when dating a document, and the demo puts the reprint date
first on the page to test exactly that.

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
  The second reviewer (v4) is aimed at that; whether it works is for the next runs to show.

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

1. Several runs per model on agent v4, with and without the extra checks, to measure what
   they add and what they cost in decoys no longer cleared.
2. A second matter written by someone else, as a held-out test.
3. An LLM extractor behind `extract.statements()`, scored against the rule-based baseline.
4. PDF and scanned-statement ingestion.

## Disclosure

All names, firms, addresses and figures in the demo matter are invented. The code was
written with substantial assistance from Claude (Anthropic); the problem definition,
the checks chosen and the review of the output are mine.

## License

All rights reserved. You may read and run this code to evaluate it; any other use needs
written permission. See [LICENSE](LICENSE).
