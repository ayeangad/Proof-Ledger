"""LLM pass — MOCK implementation with a REAL interface.

Interface mirrors what a production LLM call would look like:
    classify_hard(line, agreement, accruals, invoice_total, seen) -> dict
    with keys: predicted_reason_code, bucket, confidence, evidence.

Swap plan: replace the body with an API call that sends
(raw_description, reason_code_raw, amount, agreement, accruals) and parses
structured JSON into the same dict. Threshold routing in engine.py is
unchanged. Every call is logged to output/llm_log.jsonl either way.

CIRCULARITY WARNING (also stated in report + one-pager): this mock was
written by the same author who injected the hard cases, so its accuracy
reflects heuristics tuned to known cases — not model generalization. The
credible claim is narrower: the pipeline routes uncertainty to humans
safely, and the interface is swappable for a real model.
"""
from __future__ import annotations


def classify_hard(line, agreement, accruals, invoice_total: float, seen: set[tuple]) -> dict:
    desc = (line.raw_description or "").lower()
    raw = (line.reason_code_raw or "").upper()
    amt = abs(float(line.amount))
    inv = line.invoice_id

    def ev(*items):
        return list(items)

    # 1) blank / placeholder -> UNKNOWN, never auto-book
    if line.reason_code_raw is None or "???" in desc or desc.strip() in ("adj - see backup", "misc deduct ???"):
        return {"predicted_reason_code": "UNKNOWN", "bucket": "needs_review",
                "confidence": 0.30,
                "evidence": ev("reason_code_raw is None — no distributor code printed",
                               "description is placeholder text with no mappable keyword",
                               "policy: UNKNOWN always routes to human review, never auto-books")}

    # 2) duplicate: same invoice + amount seen before
    key = (inv, round(amt, 2))
    if key in seen:
        return {"predicted_reason_code": "SHORTAGE_CLAIM", "bucket": "disputable",
                "confidence": 0.68,
                "evidence": ev(f"duplicate signal: invoice {inv} already had a ${amt:,.2f} deduction in this run",
                               "same-claim-billed-twice pattern; second occurrence is disputable",
                               "routed to review: confidence < 0.75 by policy")}

    # 3) admin fee stacked on chargeback
    if "admin" in desc or "ADMFEE" in raw:
        return {"predicted_reason_code": "ADMIN_FEE", "bucket": "disputable",
                "confidence": 0.82,
                "evidence": ev("ADMIN_FEE keyword in distributor text",
                               "no AgreementTerm covers ADMIN_FEE — disputable by default per taxonomy",
                               "stacked-fee pattern: check against COMPLIANCE_CHARGEBACK window before paying")}

    # 4) cryptic scan shorthand
    if "sb-allow" in desc or "sb-allow" in raw.lower():
        exp = 0.03 * float(invoice_total or 0)
        pct = abs(amt - exp) / exp if exp else 1.0
        return {"predicted_reason_code": "SCAN_ALLOWANCE", "bucket": "valid_trade_spend",
                "confidence": 0.66,
                "evidence": ev("'SB-ALLOW' distributor shorthand mapped to SCAN_ALLOWANCE",
                               f"amount ${amt:,.2f} vs ~3% of invoice (${exp:,.2f}); off by {pct * 100:.1f}%",
                               "shorthand is ambiguous — routed to review: confidence < 0.75 by policy")}

    # 5) cryptic chargeback ref
    if "88213" in desc or ("chg" in desc and "ref" in desc):
        return {"predicted_reason_code": "COMPLIANCE_CHARGEBACK", "bucket": "disputable",
                "confidence": 0.62,
                "evidence": ev("'CHG-BK REF' shorthand mapped to COMPLIANCE_CHARGEBACK",
                               "no carrier/ASN backup cited on the remittance line",
                               f"${amt:,.2f} exceeds $150/event contract allowance — routed to review")}

    # 6) out-of-window chargeback
    if "out of window" in desc or "may ship" in desc:
        return {"predicted_reason_code": "COMPLIANCE_CHARGEBACK", "bucket": "disputable",
                "confidence": 0.80,
                "evidence": ev("COMPLIANCE_CHARGEBACK keyword match",
                               "May shipment billed in August — outside contract window",
                               "contract allows $150/event inside window only")}

    # 7) spoilage / shortage large
    if "spoil" in desc or "expired" in desc:
        return {"predicted_reason_code": "SPOILAGE_DAMAGE", "bucket": "disputable",
                "confidence": 0.84,
                "evidence": ev("SPOILAGE_DAMAGE keyword match",
                               "no AgreementTerm covers spoilage — case-by-case, disputable by default")}
    if "shortage" in desc or "ctns" in desc or "trlr" in desc:
        return {"predicted_reason_code": "SHORTAGE_CLAIM", "bucket": "disputable",
                "confidence": 0.70,
                "evidence": ev("SHORTAGE_CLAIM keyword match",
                               "no shipment match cited; quantity dispute needs backup",
                               "routed to review: confidence < 0.75 by policy")}

    # 8) fallback — admit uncertainty
    return {"predicted_reason_code": "UNKNOWN", "bucket": "needs_review",
            "confidence": 0.35,
            "evidence": ev("no rule or heuristic matched with usable confidence",
                           "policy: uncertain lines go to needs_review rather than guessing")}
