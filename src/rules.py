"""Rules pass — cheap deterministic matches. No LLM cost for clean lines."""
from __future__ import annotations

import re

RAW_TO_CODE = {
    "PROMO": "TRADE_PROMO", "PROMOTION": "TRADE_PROMO",
    "SCAN": "SCAN_ALLOWANCE", "BILLBACK": "SCAN_ALLOWANCE", "SB-ALLOW": "SCAN_ALLOWANCE",
    "SLOT": "SLOTTING", "SLOTTING": "SLOTTING",
    "SHORT": "SHORTAGE_CLAIM", "SHORTAGE": "SHORTAGE_CLAIM",
    "CHGBK": "COMPLIANCE_CHARGEBACK", "CHG-BK": "COMPLIANCE_CHARGEBACK", "CHARGEBACK": "COMPLIANCE_CHARGEBACK",
    "SPOIL": "SPOILAGE_DAMAGE", "DAMAGE": "SPOILAGE_DAMAGE",
    "COOP": "COOP_ADVERTISING",
    "ADMFEE": "ADMIN_FEE", "ADMIN": "ADMIN_FEE",
}

KEYWORDS = {
    "TRADE_PROMO": ["promo", "off-invoice", "allowance promo", "true-up"],
    "SCAN_ALLOWANCE": ["scan", "billback", "sb-allow"],
    "SLOTTING": ["slot", "shelf"],
    "SHORTAGE_CLAIM": ["shortage", "short ", "ctns", "trlr", "received <"],
    "COMPLIANCE_CHARGEBACK": ["chg-bk", "chgbk", "late asn", "mislabel", "violation", "ref 88"],
    "SPOILAGE_DAMAGE": ["spoil", "expired", "damage"],
    "COOP_ADVERTISING": ["coop", "flyer"],
    "ADMIN_FEE": ["admin fee", "admfee"],
}

# bucket if the code has NO contract term and NO open accrual
DEFAULT_BUCKET_NO_TERM = {
    "TRADE_PROMO": "valid_trade_spend",
    "SCAN_ALLOWANCE": "valid_trade_spend",
    "SLOTTING": "disputable",
    "SHORTAGE_CLAIM": "disputable",
    "COMPLIANCE_CHARGEBACK": "disputable",
    "SPOILAGE_DAMAGE": "disputable",
    "COOP_ADVERTISING": "disputable",
    "ADMIN_FEE": "disputable",
}


def _norm(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9\- ]", "", (s or "").upper()).strip()


def map_raw_to_code(raw_code: str | None, raw_desc: str) -> str | None:
    """Exact raw-code map first, then keyword scan of description."""
    n = _norm(raw_code)
    for key, code in RAW_TO_CODE.items():
        if key and key in n:
            return code
    d = (raw_desc or "").lower()
    for code, kws in KEYWORDS.items():
        if any(k in d for k in kws):
            return code
    return None


def _within(actual: float, expected: float, tol: float) -> tuple[bool, float]:
    if expected == 0:
        return actual == 0, 0.0
    pct = abs(actual - expected) / abs(expected)
    return pct <= tol, pct


def rules_classify(line, agreement, accruals, invoice_total: float, tol: float):
    """Return (code, bucket, conf, evidence, accrual_id) or None to defer."""
    amt = abs(float(line.amount))

    if line.reason_code_raw is None and not (line.raw_description or "").strip():
        return None
    code = map_raw_to_code(line.reason_code_raw, line.raw_description)
    if code is None:
        return None  # genuinely unmappable -> LLM/mock pass decides (likely UNKNOWN)

    # 1) open accrual match on code + amount
    for a in accruals:
        if a["reason_code"] == code and a.get("still_open"):
            ok, pct = _within(amt, float(a["accrued_amount"]), tol)
            if ok:
                return (code, "already_accrued", 0.93,
                        [f"matched PriorAccrual {a['accrual_id']} ({code}, period {a['period']})",
                         f"amount within {pct * 100:.1f}% of accrued ${a['accrued_amount']:.2f}"],
                        a["accrual_id"])

    # 2) contract term match
    term = next((t for t in agreement["terms"] if t["reason_code"] == code), None)
    if term is not None:
        evidence = [f"matched AgreementTerm {code} effective {agreement['effective_date']}"]
        bucket = "valid_trade_spend" if code in ("TRADE_PROMO", "SCAN_ALLOWANCE") else None
        if term.get("expected_amount") is not None:
            ok, pct = _within(amt, float(term["expected_amount"]), tol)
            if ok:
                b = bucket or ("valid_trade_spend" if code in ("SLOTTING", "COOP_ADVERTISING") else "disputable")
                return (code, b, 0.91,
                        evidence + [f"amount within {pct * 100:.1f}% of contracted ${term['expected_amount']:.2f}"],
                        None)
            # flat term exists but amount off -> not a clean match; defer (could be partial/duplicate)
            if code in ("SLOTTING", "COMPLIANCE_CHARGEBACK"):
                return None
        if term.get("expected_pct_of_invoice") is not None and invoice_total:
            exp = float(term["expected_pct_of_invoice"]) * float(invoice_total)
            ok, pct = _within(amt, exp, tol)
            if ok:
                return (code, "valid_trade_spend", 0.90,
                        evidence + [f"amount within {pct * 100:.1f}% of {term['expected_pct_of_invoice'] * 100:.0f}% of invoice ${invoice_total:,.2f}"],
                        None)
            return None  # pct term exists but off -> ambiguous, defer
        # term exists, no amount anchor (shouldn't happen for our terms) -> medium conf valid/disputable
        b = bucket or "disputable"
        return (code, b, 0.78, evidence + ["no amount anchor in term; keyword + raw-code match only"], None)

    # 3) no term, no accrual -> disputable codes classify directly w/ high conf
    if code in DEFAULT_BUCKET_NO_TERM:
        b = DEFAULT_BUCKET_NO_TERM[code]
        conf = 0.88 if b == "disputable" else 0.80
        return (code, b, conf,
                [f"keyword/raw-code map to {code}",
                 "no AgreementTerm and no open PriorAccrual — default bucket per taxonomy"], None)
    return None
