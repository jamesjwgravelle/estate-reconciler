# Estate Reconciler: a one-page guide for lawyers

## What it is for

You act for a beneficiary. The executor has produced a statement of accounts, bank
statements and a run of letters. Before you can ask useful questions, someone has to
check each against the others. This tool does that first pass and hands you a list of
discrepancies, each with the passages it relies on.

It does not decide whether anyone did anything wrong, and it does not replace your
review. It tells you where to look.

## What you give it

A folder containing the accounts, the bank record and the correspondence. Set up as
recommended, with a model running on your own computer, no document leaves it.

## What you get back

**A lawyer's report.** A dollar total, a table by category, and one entry per
discrepancy, most serious first. Each entry shows what two documents say, where they
differ, the amount, and the exact lines quoted from each.

**A client summary.** The same items, with the same numbering, in plain language and
without citations. It is a draft for you to review and edit before it goes to the client.

**A schedule.** The items as a spreadsheet (CSV), one row each, for your own working papers.

**A verdict on each entry.** Before an item reaches you, the tool looks through the file
for an innocent explanation.

| Verdict | What it means | What you do |
|---|---|---|
| Stands | It looked and found no explanation in the file. | Raise it. |
| Needs a lawyer's review | It found something partial, or the question is one of judgment. | Read the note and decide. |
| Explained by the file | The file itself accounts for it, for example one invoice paid by two cheques. | Spot-check the cited lines, then set it aside. |

**A draft request letter.** It lists every item that was not explained, with its source.
It is a draft. Nothing is ever sent for you.

## How to read an entry

1. Read the title. It states the discrepancy in one line.
2. Open the quoted passages in the original documents and confirm they say what the
   report says they say. Do this for every item you intend to rely on.
3. Read the verdict and its note. Where the tool overrode itself, the note says why.
4. Decide. The tool's verdict is a recommendation.

## How to read the dollar figure

The "amount in question" is the sum of the individual discrepancies that are still open.

- **Nothing is counted twice.** A total that does not add up, or a balance that does not
  match the bank, is a symptom of the items behind it. Those amounts are shown but not added.
- **Explained items are left out.** Once the tool has investigated, anything the file
  itself accounts for is set aside.
- **It is not a damages figure.** It tells you how much money the open questions touch,
  not what was lost or what is owed. Say so when you give the number to a client.

The balance bridge in the lawyer's report shows how the individual items add up to the
gap between the balance the accounts state and the balance at the bank. If the
"unexplained residual" is not zero, something moved the balance that the tool has not
identified, and that is worth a question of its own.

## What it checks

- Every accounts entry against the bank record, and every bank transaction against the accounts
- Whether the accounts add up and the stated balance matches the bank
- Documents a letter says are enclosed or coming that are not in the file
- Letters that describe a document as outstanding after the date on the document
- Figures quoted in letters against the records
- Executor compensation against a starting-point guideline you can set
- Gifts of money in the will against the payments in the accounts
- Penalties and late charges paid out of the estate
- Lawyers' invoices paid by the estate: whether they add up, entries billed twice, and
  time that looks like advice to the executor personally
- Letters against the lawyers' own time records
- Forms dated well before they were signed, and the gap between the final tax assessment
  and the clearance certificate application
- Fees paid to an agent (such as a trust company) alongside full executor compensation
- Tax payments on a reassessment against the notices actually produced

## How cautious it is

The tool is built so that its mistakes fall on the safe side.

- It will sometimes send you an item that turns out to be fine. That costs you a few minutes.
- It is designed not to clear an item that is a real problem. An item is marked
  "explained" only if three separate passes agree, an independent check confirms it, and
  the explanation cites specific lines in the file.
- A total that does not add up is never marked "explained", whatever else is in the file.
- Questions of judgment, such as whether compensation is reasonable, always come to you.

## What it cannot do yet

- Read scanned or photographed statements. It needs text or spreadsheet exports.
- Recognise a promise that is worded loosely ("you should have the appraisal shortly").
- Handle more than one bank account in a single pass.
- Tell you what the law requires. The compensation guideline is a rule of thumb, not a ruling.

## Three habits that keep it reliable

1. Check the citation before you repeat the claim.
2. Treat "explained" as "probably fine", not "confirmed".
3. If an item you expected is missing from the report, do not assume it was cleared. Check
   it yourself; the tool only sees what is in the folder.
