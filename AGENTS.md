# Working on this project (for people and coding assistants)

Read this file before changing anything. It is written so that one small task can be done
at a time, by a person or by a coding assistant of any size.

## The one command

```
python verify.py
```

It regenerates the demo matter, runs the tests, runs the stage 1 eval and builds the
reports. It needs no model. **A change is not finished until this prints PASS.** If it
fails, fix the cause; do not edit a test or `evals/ground_truth.json` to make it pass
unless the task says the expected result has changed.

## Map

| Path | What it holds |
|---|---|
| `reconciler/rules/*.py` | One check per file. This is where most new work goes. |
| `reconciler/rules/_template.py` | Copy this to start a new check. |
| `reconciler/catalog.py` | One entry per finding type: label, report category, whether its amount is added to the total, request-letter wording. |
| `reconciler/checks.py` | Registry and `Config` (tolerances). Loads every rule file automatically. |
| `reconciler/summary.py` | Dollar totals and the balance bridge. |
| `reconciler/report.py` | Lawyer report, client summary, CSV schedule. |
| `reconciler/agent.py`, `tools.py` | The investigator and its read-only tools. |
| `reconciler/ingest.py`, `extract.py` | Loading a matter folder; turning letters into statements. |
| `reconciler/invoices.py` | Parses a lawyer's invoice (text) into time entries and stated totals. |
| `make_demo.py` | Builds the fictional demo matter. `seeded` plants real problems, `decoys` plants look-alikes. |
| `evals/ground_truth.json` | The label for every finding the demo matter should raise. |
| `tests/` | Unit tests. `test_agent.py` uses a scripted stand-in for the model. |

## Rules that must not be broken

1. **Code does the arithmetic.** Sums, matching and date comparisons are written in Python
   with `Decimal`. A model is never asked to add, compare or reconcile.
2. **Every finding cites evidence.** At least one `Evidence` with a real file and location.
3. **Findings describe documents, not people.** Say what two sources show and where they
   differ. No words like fraud, theft, hid or lied.
4. **Unsafe outcomes fall to a human.** Any new error path in the agent must end in
   `needs_human`, never in `explained`.
5. **No double counting.** If a new finding's amount overlaps with other findings, set
   `counted=False` for its type in the catalog.
6. **The clean control stays clean.** `build(seeded=False, decoys=False)` must raise nothing.
7. **Only fictional data.** Never add a real person, firm, account or document to this repo.
8. **No new dependencies** without a reason written in the README. The core runs on the
   standard library.

## Recipe: add a check

1. Copy `reconciler/rules/_template.py` to `reconciler/rules/<name>.py` and write the check.
   Set `amount` if there is a dollar figure, and `plain` (a sentence a client could read).
   If the finding changes the cash balance, set `balance_effect`; see `ledger.py` for the sign.
2. Add the finding type to `reconciler/catalog.py`.
3. In `make_demo.py`, plant one example that appears only when `seeded=True`. Keep the
   books consistent: if you add an accounts entry, add the matching bank line unless the
   mismatch is the point.
4. Add the expected finding to `evals/ground_truth.json` with `"label": "real"`.
5. If the demo changed, bump `DATASET_VERSION` in `make_demo.py`.
6. Run `python evals/make_table.py --write` to regenerate the README counts, and add the
   check to the lists in `README.md` and `GUIDE.md`.
7. Run `python verify.py`.

To add a decoy instead (something that looks wrong but is explained in the file): plant
it when `decoys=True`, label it `"decoy"`, and add a line to
`test_tools_can_reach_every_decoy_explanation` proving the explanation can be found with
the agent's tools. An unfindable decoy makes the eval unfair.

## When the agent changes

Any change to the prompt or to a rule in `agent.py`: bump `AGENT_VERSION`, add a test for
the behaviour in `tests/test_agent.py`, then re-run `python evals/run_agent_eval.py` and
`python evals/make_table.py --write`. Never type a result into the README by hand.

## Backlog: small tasks, one at a time

Each is sized to be done alone. "Done when" is the acceptance test.

1. **Duplicate payment.** Two bank debits to the same payee for the same amount within 30
   days, with one accounts entry. New rule file. *Done when:* a seeded duplicate is raised
   as `duplicate_payment`, counted, and `verify.py` passes.
2. **Payment to the executor.** Flag any bank debit whose description names the executor
   (take the name from the will's "I appoint ... as Executor" line) and that is not
   described as compensation. *Done when:* the demo's $5,000 e-transfer gains a second,
   uncounted finding `payment_to_executor`, and the catalog marks it `counted=False`.
3. **Distribution check.** If the will divides the residue "equally among" N named people,
   compare with distribution entries. Needs names in the will first. *Done when:* an
   unequal seeded distribution is raised.
4. **Text PDFs.** `ingest.py` already reads `.pdf` letters when `pypdf` is installed. Add a
   test with a generated PDF letter. *Done when:* a PDF letter produces the same findings
   as its `.txt` twin.
5. **Looser promise wording.** Extend `PROMISE` in `extract.py` to catch "should reach you
   shortly" and "under separate cover". Add one seeded example and one sentence that must
   NOT match. *Done when:* both are tested.
6. **Second bank account.** Let `bank*.csv` be several files, each with its own closing
   balance. *Done when:* a transfer between two estate accounts raises nothing.
7. **Configurable guideline.** Read `Config` overrides from an optional `config.json` in
   the matter folder. *Done when:* a 2% rate in the file changes the compensation finding.
8. **Invoice against the accounts.** Compare each invoice's "Total due" with the accounts
   entry that pays it (same firm name, nearest date). *Done when:* a seeded difference is
   raised as `invoice_vs_accounts` and the clean control stays clean.
9. **Hours times rate.** Flag a time entry whose amount is not hours x rate. *Done when:*
   one seeded entry is raised and counted.
10. **Compensation threats in letters.** Flag a letter that says compensation will rise if a
    passing of accounts is required, quoting it neutrally. *Done when:* one seeded sentence is
    raised, one sentence merely mentioning compensation is not, and the finding goes to a
    lawyer by rule (add its type to `JUDGMENT_ONLY`).
11. **Second demo matter.** A new estate with different names and at least three new traps,
   written by someone who has not read `rules/`. This is the most valuable item on the list.

Not on the list on purpose: a web interface, a vector database, more agents. None of them
changes what the tool can prove.

## Using a small model as the coding assistant

- Give it one backlog item and this file. Not the whole repository.
- Point it at the two or three files the task names, plus `_template.py`.
- Have it run `python verify.py` and paste the output. Accept nothing without PASS.
- Read the diff yourself. Check rule 3 (no accusations) and rule 5 (no double counting);
  those are judgment calls a test cannot fully catch.
