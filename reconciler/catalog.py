"""One entry per finding type. The reports, the totals and the request letter all read from here.

Adding a check means adding its type here; a test fails if a check raises a type that is
missing from this table.

`counted` decides whether a finding's amount is added to the report's "amount in question".
It is False where adding it would count the same dollars twice (a wrong total is a symptom
of the items behind it) or where no money is in doubt (a payment made on a different date).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeInfo:
    label: str       # short name for tables
    category: str    # heading the finding is grouped under in the reports
    counted: bool    # add its amount to the total?
    ask: str         # what the request letter asks for


LEDGER = "Accounts and bank records disagree"
TOTALS = "Totals and balances (not added: these overlap with the items above)"
LETTERS = "Letters disagree with the records"
COMP = "Executor compensation"
WILL = "Gifts in the will not shown as paid"
COSTS = "Costs charged to the estate that may be avoidable"
TAX = "Tax payments without the notice behind them"
FEES = "Legal fees charged to the estate"
DOCS = "Documents and statements about them"
TIMING = "Timing (no amount in doubt)"

# The order here is the order categories appear in the reports.
CATALOG: dict[str, TypeInfo] = {
    "unsupported_entry": TypeInfo(
        "Payment in the accounts, not at the bank", LEDGER, True,
        "Please produce the voucher for this item and identify the account from which it was paid."),
    "undisclosed_transaction": TypeInfo(
        "Bank transaction missing from the accounts", LEDGER, True,
        "Please identify the payee and purpose of this transaction and explain why it does not appear in the accounts."),
    "amount_mismatch": TypeInfo(
        "Different amount in the accounts and at the bank", LEDGER, True,
        "Please explain the difference and produce the invoice and the cheque image or payment record."),
    "letter_vs_records": TypeInfo(
        "Figure in a letter differs from the records", LETTERS, True,
        "Please confirm which figure is correct and produce the supporting document."),
    "compensation_review": TypeInfo(
        "Compensation above the guideline", COMP, True,
        "Please provide the basis for the compensation claimed, including any record of time spent."),
    "agent_fee_offset": TypeInfo(
        "Agent fees paid as well as full compensation", COMP, False,   # overlaps with compensation_review
        "Please explain what administration the executor performed personally, and whether compensation "
        "has been adjusted for the fees paid to the agent."),
    "unpaid_bequest": TypeInfo(
        "Gift in the will with no payment shown", WILL, True,
        "Please confirm whether this gift has been paid and, if so, produce the record of payment."),
    "avoidable_cost": TypeInfo(
        "Penalty or late charge paid by the estate", COSTS, True,
        "Please explain how this charge arose and why it was paid from the estate."),
    "unsupported_tax_payment": TypeInfo(
        "Tax payment without the notice behind it", TAX, True,
        "Please produce the Notice of Reassessment to which this payment relates."),
    "invoice_arithmetic": TypeInfo(
        "Invoice does not add up", FEES, True,
        "Please provide a corrected invoice or the time records that support the fees billed."),
    "duplicate_time_entry": TypeInfo(
        "Time entry billed twice", FEES, True,
        "Please confirm whether this entry was billed twice and, if so, that the estate has been credited."),
    "personal_legal_fees": TypeInfo(
        "Possible personal advice billed to the estate", FEES, True,
        "Please explain why this work was charged to the estate rather than to the executor personally."),
    "missing_document": TypeInfo(
        "Document not produced", DOCS, False,
        "Please produce this document."),
    "timeline_contradiction": TypeInfo(
        "Letter contradicts a document's date", DOCS, False,
        "Please confirm the date on which this document was received, and by whom."),
    "billing_contradiction": TypeInfo(
        "Letter contradicts the lawyers' time records", DOCS, False,
        "Please confirm when this document was first received by the executor or her counsel."),
    "document_date_conflict": TypeInfo(
        "Form dated well before it was signed", DOCS, False,
        "Please confirm the date on which this form was signed and submitted."),
    "arithmetic_error": TypeInfo(
        "Total does not add up", TOTALS, False,
        "Please provide a corrected summary of accounts."),
    "balance_mismatch": TypeInfo(
        "Stated balance differs from the bank", TOTALS, False,
        "Please provide a reconciliation of the stated balance to the bank balance."),
    "date_mismatch": TypeInfo(
        "Different date in the accounts and at the bank", TIMING, False,
        "Please confirm the date on which this payment was made."),
    "clearance_delay": TypeInfo(
        "Delay between final assessment and clearance application", TIMING, False,
        "Please explain the interval between the final assessment and the application for the clearance certificate."),
}

FALLBACK = TypeInfo("Other", "Other", False, "Please provide an explanation.")


def info(finding_type: str) -> TypeInfo:
    return CATALOG.get(finding_type, FALLBACK)
