"""Reconciliation engine — rules pass, then mock-LLM pass, then safety routing."""
from __future__ import annotations

import json
from pathlib import Path

from .llm_mock import classify_hard
from .rules import rules_classify

ROOT = Path(__file__).resolve().parents[1]


def reconcile(remittances, agreement, accruals, cfg) -> tuple[list[dict], list[dict]]:
    tol = float(cfg["amount_tolerance"])
    thr = float(cfg["confidence_threshold"])
    dollar_thr = float(cfg["disputable_review_threshold"])
    decisions, llm_log = [], []
    seen: set[tuple] = set()
    je_seq = 0

    for rem in remittances:
        inv_total = float(rem.invoice_total)
        for ln in rem.lines:
            r = rules_classify(ln, agreement, accruals, inv_total, tol)
            if r is not None:
                code, bucket, conf, evidence, accrual_id = r
                stage = "rules"
            else:
                h = classify_hard(ln, agreement, accruals, inv_total, seen)
                code, bucket, conf = h["predicted_reason_code"], h["bucket"], float(h["confidence"])
                evidence, accrual_id, stage = h["evidence"], None, "llm_mock"
                llm_log.append({
                    "line_id": ln.line_id,
                    "prompt_context": {
                        "raw_description": ln.raw_description,
                        "reason_code_raw": ln.reason_code_raw,
                        "amount": ln.amount,
                        "invoice_id": ln.invoice_id,
                        "agreement_terms": [t["reason_code"] for t in agreement["terms"]],
                        "open_accruals": [a["accrual_id"] for a in accruals if a.get("still_open")],
                    },
                    "response": h,
                })

            # ---- safety routing: model never gets final say on money above threshold
            pre_route_bucket = bucket
            routed = False
            if code == "UNKNOWN":
                bucket, conf, routed = "needs_review", min(conf, 0.45), True
                evidence = evidence + ["policy: UNKNOWN always routes to human review, never auto-books"]
            elif conf < thr:
                evidence = evidence + [f"policy: confidence {conf:.2f} < {thr:.2f} — forced to needs_review"]
                bucket, routed = "needs_review", True
            elif bucket == "disputable" and abs(float(ln.amount)) > dollar_thr:
                evidence = evidence + [f"policy: disputable ${abs(float(ln.amount)):,.2f} > ${dollar_thr:,.0f} — forced to needs_review"]
                bucket, routed = "needs_review", True

            je_seq += 1
            decisions.append({
                "line_id": ln.line_id, "predicted_reason_code": code, "bucket": bucket,
                "confidence": round(float(conf), 3), "evidence": evidence,
                "matched_accrual_id": accrual_id,
                "journal_entry_id": f"JE-{je_seq:05d}", "stage": stage,
                "routed_to_review": routed, "raw_confidence": round(float(conf), 3),
                "pre_route_bucket": pre_route_bucket,
                "amount": float(ln.amount), "raw_description": ln.raw_description,
                "reason_code_raw": ln.reason_code_raw, "invoice_id": ln.invoice_id,
                "remittance_id": rem.remittance_id, "distributor_id": ln.distributor_id,
            })
            seen.add((ln.invoice_id, round(abs(float(ln.amount)), 2)))
    return decisions, llm_log
