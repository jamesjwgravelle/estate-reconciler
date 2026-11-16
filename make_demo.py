"""Generate the fictional demo matter.

    python make_demo.py                     -> demo_matter/ (planted problems and decoys)
    build(path, seeded=False, decoys=False) -> a fully consistent file; the tests use it as
                                               a true-negative control

"seeded" plants real problems. "decoys" plants things that look like problems to the first
pass but are explained elsewhere in the file (a split payment, a reversed wire, a document
filed under another name). The investigator agent is scored on telling the two apart.

Every person, firm, address and figure here is invented.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path


def build(root: str | Path, seeded: bool = True, decoys: bool = True) -> None:
    root = Path(root)
    (root / "correspondence").mkdir(parents=True, exist_ok=True)
    S, D = seeded, decoys

    comp = "32000.00" if S else "16000.00"
    accounts = [
        ("R-01", "2023-03-20", "receipt", "Transfer in - deceased's chequing account closing balance", "48310.22"),
        ("R-02", "2023-04-11", "receipt", "Life insurance proceeds - Lakeshore Mutual", "25000.00"),
        ("R-03", "2023-09-15", "receipt", "Sale of 14 Alder Lane - net proceeds", "398500.00"),
        ("R-04", "2023-10-02", "receipt", "Sale of vehicle - 2016 Subaru", "9800.00"),
        ("R-05", "2024-02-28", "receipt", "CRA refund - terminal return", "1942.67"),
        ("D-01", "2023-03-28", "disbursement", "Funeral - Hillcrest Funeral Home", "11200.00"),
        ("D-02", "2023-04-05", "disbursement", "Probate fees - Minister of Finance", "2105.00"),
        ("D-03", "2023-05-12", "disbursement", "Property insurance - 14 Alder Lane", "1380.00"),
        ("D-04", "2023-06-20", "disbursement", "Roof repair - Keller Contracting", "8450.00"),
        ("D-05", "2023-07-03", "disbursement", "Property taxes - City of Kingston", "3212.40"),
        ("D-10", "2023-08-01", "disbursement", "Utilities - final hydro account", "412.18"),
        # decoy: one accounts entry, paid by two cheques a fortnight apart
        *([("D-11", "2023-08-14", "disbursement", "House cleanout - Brightway Haulage", "3600.00")] if D else []),
        ("D-06", "2023-09-18", "disbursement", "Legal fees - Whitlock & Pryce LLP", "14690.00"),
        ("D-07", "2023-11-06", "disbursement", "Accounting fees - Brandt CPA", "2825.00"),
        ("D-08", "2024-01-15", "disbursement", "Interim distribution to beneficiaries", "150000.00"),
        ("D-09", "2024-03-01", "disbursement", "Executor compensation", comp),
    ]
    with (root / "accounts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entry_id", "date", "type", "description", "amount"])
        w.writerows(accounts)

    receipts = sum(Decimal(a[4]) for a in accounts if a[2] == "receipt")
    disb = sum(Decimal(a[4]) for a in accounts if a[2] == "disbursement")
    stated_disb = disb + Decimal("5000") if S else disb          # seeded: totals do not add up
    (root / "accounts_summary.txt").write_text(
        "ESTATE OF MARGARET ELLEN HARTWELL - SUMMARY OF ACCOUNTS\n"
        "Period: 2023-03-04 to 2024-03-31\n"
        f"Total receipts: ${receipts:,.2f}\n"
        f"Total disbursements: ${stated_disb:,.2f}\n"
        f"Balance on hand: ${receipts - stated_disb:,.2f}\n", encoding="utf-8")

    # (date, description, debit, credit)
    bank = [
        ("2023-03-20", "TRANSFER IN CLOSED ACCT M HARTWELL", "", "48310.22"),
        ("2023-03-29", "CHQ 101 HILLCREST FUNERAL HOME", "9200.00" if S else "11200.00", ""),
        ("2023-04-05", "CHQ 102 MINISTER OF FINANCE PROBATE", "2105.00", ""),
        ("2023-04-12", "DEPOSIT LAKESHORE MUTUAL LIFE", "", "25000.00"),
        ("2023-04-28", "MONTHLY ACCOUNT FEE", "4.95", ""),
        ("2023-05-12", "PAD NORTHGATE INSURANCE", "1380.00", ""),
        *([] if S else [("2023-06-21", "CHQ 103 KELLER CONTRACTING", "8450.00", "")]),
        ("2023-07-04", "CITY OF KINGSTON TAX PAYMENT", "3212.40", ""),
        ("2023-08-02", "HYDRO BILL PAYMENT", "412.18", ""),
        *([("2023-08-14", "CHQ 106 BRIGHTWAY HAULAGE DEPOSIT", "1800.00", ""),
           ("2023-08-28", "CHQ 107 BRIGHTWAY HAULAGE BALANCE", "1800.00", ""),
           # decoy: a wire sent in error and reversed two days later
           ("2023-09-05", "WIRE OUT REF 77812", "1250.00", ""),
           ("2023-09-07", "REVERSAL WIRE OUT REF 77812", "", "1250.00")] if D else []),
        ("2023-09-15", "WIRE IN WHITLOCK PRYCE TRUST - ALDER LANE", "", "398500.00"),
        ("2023-09-19", "CHQ 104 WHITLOCK PRYCE LLP", "14690.00", ""),
        ("2023-10-02", "DEPOSIT VEHICLE SALE", "", "9800.00"),
        *([("2023-10-20", "E-TRANSFER TO D COLBY", "5000.00", "")] if S else []),
        ("2023-10-31", "MONTHLY ACCOUNT FEE", "4.95", ""),
        ("2023-12-19" if S else "2023-11-07", "CHQ 105 BRANDT CPA", "2825.00", ""),
        ("2024-01-15", "WIRE OUT BENEFICIARY DISTRIBUTION", "150000.00", ""),
        ("2024-02-28", "CANADA REVENUE AGENCY REFUND", "", "1942.67"),
        ("2024-03-01", "TRANSFER TO D COLBY EXECUTOR COMPENSATION", comp, ""),
    ]
    bank.sort(key=lambda r: r[0])
    balance = Decimal(0)
    with (root / "bank_statement.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "debit", "credit", "balance"])
        for d, desc, debit, credit in bank:
            balance += Decimal(credit or "0") - Decimal(debit or "0")
            w.writerow([d, desc, debit, credit, f"{balance:.2f}"])

    (root / "will.txt").write_text(
        "LAST WILL AND TESTAMENT OF MARGARET ELLEN HARTWELL\n"
        "Date: 2019-06-03\n\n"
        "I appoint my niece, Diane Colby, as Executor and Trustee of my Estate.\n"
        "I direct that the residue of my Estate be divided equally among my grandchildren.\n",
        encoding="utf-8")

    (root / "cra_notice_of_assessment_2023.txt").write_text(
        "NOTICE OF ASSESSMENT - T3 TRUST INCOME TAX\n"
        "Date issued: 2024-12-17\n"
        "Addressed to: Estate of Margaret Ellen Hartwell, c/o Northshore Trust Company\n\n"
        "Tax year: 2023\n"
        "Balance owing: $0.00\n", encoding="utf-8")

    if D:
        # decoy: the promised inventory is in the file, but is not called an inventory
        (root / "schedule_a_assets.txt").write_text(
            "SCHEDULE A - ASSETS OF THE ESTATE AT DATE OF DEATH\n"
            "Date: 2023-04-20\n"
            "Prepared by the Executor, Diane Colby\n\n"
            "1. Chequing account, closing balance $48,310.22\n"
            "2. Life insurance policy, Lakeshore Mutual, $25,000.00\n"
            "3. House and lot at 14 Alder Lane, Kingston (to be valued)\n"
            "4. 2016 Subaru\n"
            "5. Household contents\n", encoding="utf-8")

    head = "From: Whitlock & Pryce LLP (counsel to the Executor)\nTo: Adeyemi Law (counsel to a beneficiary)\nRe: Estate of Margaret Ellen Hartwell\n\n"

    (root / "correspondence" / "2023-05-02_letter.txt").write_text(
        "Date: 2023-05-02\n" + head +
        "Enclosed please find a copy of the Will.\n" +
        ("An inventory of what the deceased owned will be provided under separate cover.\n" if D else "") +
        ("We will provide the appraisal of 14 Alder Lane once it is received from the appraiser.\n" if S else "") +
        "The Executor intends to list the property for sale this summer.\n", encoding="utf-8")

    price = "412,000" if S else "398,500"
    (root / "correspondence" / "2023-10-05_letter.txt").write_text(
        "Date: 2023-10-05\n" + head +
        f"The property at 14 Alder Lane has sold, and the sale generated net proceeds of ${price} to the Estate.\n" +
        ("The Executor will provide the T3 trust returns for 2023 together with her accounting.\n" if S else "") +
        "An interim distribution is expected in the new year.\n", encoding="utf-8")

    late = "2025-06-10" if S else "2024-11-01"   # clean file: letter predates the Notice of Assessment
    (root / "correspondence" / f"{late}_letter.txt").write_text(
        f"Date: {late}\n" + head +
        "A statement of accounts is enclosed.\n"
        "An interim distribution of $150,000 was made in January 2024.\n"
        "The Executor is still waiting on the Notice of Assessment from CRA and cannot apply for the clearance certificate until it arrives.\n",
        encoding="utf-8")


if __name__ == "__main__":
    import shutil
    target = Path(__file__).parent / "demo_matter"
    shutil.rmtree(target, ignore_errors=True)
    build(target)
    print("wrote demo_matter/")
