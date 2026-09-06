"""Pydantic schemas — the deliverable people judge. Provenance first."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

REASON_CODES = (
    "TRADE_PROMO",
    "SCAN_ALLOWANCE",
    "SLOTTING",
    "SHORTAGE_CLAIM",
    "COMPLIANCE_CHARGEBACK",
    "SPOILAGE_DAMAGE",
    "COOP_ADVERTISING",
    "ADMIN_FEE",
    "UNKNOWN",
)

ReasonCode = Literal[
    "TRADE_PROMO",
    "SCAN_ALLOWANCE",
    "SLOTTING",
    "SHORTAGE_CLAIM",
    "COMPLIANCE_CHARGEBACK",
    "SPOILAGE_DAMAGE",
    "COOP_ADVERTISING",
    "ADMIN_FEE",
    "UNKNOWN",
]

Bucket = Literal["already_accrued", "valid_trade_spend", "disputable", "needs_review"]


class AgreementTerm(BaseModel):
    reason_code: ReasonCode
    description: str
    expected_amount: float | None = None
    expected_pct_of_invoice: float | None = None
    max_amount_per_period: float | None = None


class TradeSpendAgreement(BaseModel):
    brand_id: str
    distributor_id: str
    effective_date: date
    expiration_date: date
    terms: list[AgreementTerm]


class PriorAccrual(BaseModel):
    accrual_id: str
    period: str
    reason_code: ReasonCode
    accrued_amount: float
    still_open: bool


class RemittanceLine(BaseModel):
    line_id: str
    distributor_id: str
    invoice_id: str
    remittance_date: date
    raw_description: str
    reason_code_raw: str | None = None
    amount: float  # negative = deducted from brand


class Remittance(BaseModel):
    remittance_id: str
    distributor_id: str
    brand_id: str
    remittance_date: date
    invoice_total: float
    cash_received: float
    lines: list[RemittanceLine]


class Decision(BaseModel):
    line_id: str
    predicted_reason_code: ReasonCode
    bucket: Bucket
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(min_length=1)
    matched_accrual_id: str | None = None
    journal_entry_id: str
    stage: str = "rules"  # "rules" | "llm_mock" — which pass produced it


class JournalEntry(BaseModel):
    entry_id: str
    period: str
    debit_account: str
    credit_account: str
    amount: float
    source_line_id: str
    memo: str
    status: Literal["auto_posted", "pending_review", "disputed"]

    @field_validator("source_line_id")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        assert v.strip(), "source_line_id is non-negotiable"
        return v
