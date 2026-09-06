"""Ledger — every Decision becomes a JournalEntry with source_line_id provenance."""
from __future__ import annotations


def period_of(remittance_id: str) -> str:
    # REM-202607-003 -> 2026-07
    try:
        return remittance_id.split("-")[1][:4] + "-" + remittance_id.split("-")[1][4:6]
    except Exception:
        return "2026-07"


def to_journal(d: dict) -> dict:
    amt = round(abs(float(d["amount"])), 2)
    period = period_of(d.get("remittance_id", ""))
    memo = f"{d['predicted_reason_code']} | {d.get('raw_description','')[:60]} | {d['line_id']}"
    b = d["bucket"]
    if b == "already_accrued":
        return {"entry_id": d["journal_entry_id"], "period": period,
                "debit_account": "Accrued Trade Spend Liability",
                "credit_account": "AR — Distributor",
                "amount": amt, "source_line_id": d["line_id"], "memo": memo,
                "status": "auto_posted"}
    if b == "valid_trade_spend":
        return {"entry_id": d["journal_entry_id"], "period": period,
                "debit_account": "Trade Promotion Expense (contra-revenue)",
                "credit_account": "AR — Distributor",
                "amount": amt, "source_line_id": d["line_id"], "memo": memo,
                "status": "auto_posted"}
    if b == "disputable":
        return {"entry_id": d["journal_entry_id"], "period": period,
                "debit_account": "Deductions Receivable — Disputed",
                "credit_account": "AR — Distributor",
                "amount": amt, "source_line_id": d["line_id"], "memo": memo,
                "status": "disputed"}
    return {"entry_id": d["journal_entry_id"], "period": period,
            "debit_account": "DRAFT — pending review",
            "credit_account": "AR — Distributor",
            "amount": amt, "source_line_id": d["line_id"], "memo": memo,
            "status": "pending_review"}


def build_ledger(decisions: list[dict]) -> list[dict]:
    return [to_journal(d) for d in decisions]


def review_queue_rows(decisions: list[dict]) -> list[dict]:
    rows = [d for d in decisions if d["bucket"] == "needs_review"]
    return sorted(rows, key=lambda d: abs(float(d["amount"])), reverse=True)
