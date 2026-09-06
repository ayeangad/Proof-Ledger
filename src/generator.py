"""Synthetic data generator — fictional brand, seeded, hand-labeled ground truth.

Ground truth discipline: every line is created WITH its intended label
(gt_code, gt_bucket) decided by the author at creation time. The engine
(rules.py / llm_mock.py) is never consulted here. That separation is what
makes ground_truth.json an answer key instead of an echo.
"""
from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REMIT_DIR = DATA / "remittances"

BRAND = "Northfork Snack Co."
BRAND_ID = "BRAND-NORTHFORK"
DIST_UNFI = "DIST-UNFI-SYN"
DIST_KEHE = "DIST-KEHE-SYN"

# ---------------------------------------------------------------- helpers

_line_seq = 0
_gt: dict[str, dict] = {}


def _lid(prefix: str) -> str:
    global _line_seq
    _line_seq += 1
    return f"{prefix}-L{_line_seq:04d}"


def _line(dist, inv, dt, raw, raw_code, amount, gt_code, gt_bucket, lid=None):
    line_id = lid or _lid(inv)
    _gt[line_id] = {"reason_code": gt_code, "bucket": gt_bucket}
    return {
        "line_id": line_id,
        "distributor_id": dist,
        "invoice_id": inv,
        "remittance_date": dt.isoformat(),
        "raw_description": raw,
        "reason_code_raw": raw_code,
        "amount": round(amount, 2),
    }


def _rem(rem_id, dist, dt, inv_total, lines):
    deducted = round(sum(abs(float(l["amount"])) for l in lines), 2)
    return {
        "remittance_id": rem_id,
        "distributor_id": dist,
        "brand_id": BRAND_ID,
        "remittance_date": dt.isoformat(),
        "invoice_total": round(inv_total, 2),
        "cash_received": round(inv_total - deducted, 2),
        "lines": lines,
    }


# ---------------------------------------------------------------- main

def generate(seed: int = 42) -> dict:
    global _line_seq, _gt
    _line_seq = 0
    _gt = {}
    rng = random.Random(seed)

    agreement = {
        "brand_id": BRAND_ID,
        "distributor_id": "MULTI",
        "effective_date": "2026-06-01",
        "expiration_date": "2026-12-31",
        "terms": [
            {"reason_code": "TRADE_PROMO", "description": "Q3 off-invoice promo 8% of invoice",
             "expected_amount": None, "expected_pct_of_invoice": 0.08, "max_amount_per_period": 5000.0},
            {"reason_code": "SCAN_ALLOWANCE", "description": "Scan billback ~3% of invoice",
             "expected_amount": None, "expected_pct_of_invoice": 0.03, "max_amount_per_period": 2500.0},
            {"reason_code": "SLOTTING", "description": "Shelf placement Q3 installment",
             "expected_amount": 1500.0, "expected_pct_of_invoice": None, "max_amount_per_period": 1500.0},
            {"reason_code": "COOP_ADVERTISING", "description": "Co-op flyer 2% capped at $2000",
             "expected_amount": None, "expected_pct_of_invoice": 0.02, "max_amount_per_period": 2000.0},
            {"reason_code": "COMPLIANCE_CHARGEBACK", "description": "Late-ASN/label violations, max $150 per event inside window",
             "expected_amount": 150.0, "expected_pct_of_invoice": None, "max_amount_per_period": 600.0},
            {"reason_code": "SHORTAGE_CLAIM", "description": "No standing term — case-by-case, disputable by default",
             "expected_amount": None, "expected_pct_of_invoice": None, "max_amount_per_period": None},
            {"reason_code": "SPOILAGE_DAMAGE", "description": "No standing term — case-by-case, disputable by default",
             "expected_amount": None, "expected_pct_of_invoice": None, "max_amount_per_period": None},
        ],
    }

    accruals = [
        {"accrual_id": "ACC-001", "period": "2026-07", "reason_code": "TRADE_PROMO",
         "accrued_amount": 1840.0, "still_open": True},
        {"accrual_id": "ACC-002", "period": "2026-07", "reason_code": "SLOTTING",
         "accrued_amount": 1500.0, "still_open": True},
        {"accrual_id": "ACC-003", "period": "2026-06", "reason_code": "COOP_ADVERTISING",
         "accrued_amount": 640.0, "still_open": False},
        {"accrual_id": "ACC-004", "period": "2026-07", "reason_code": "SCAN_ALLOWANCE",
         "accrued_amount": 690.0, "still_open": True},
    ]

    remittances = []
    months = [(2026, 6), (2026, 7), (2026, 8)]

    # ---- easy-line factories (clean matches, deterministic labels)
    def easy_trade_promo(dist, inv, dt, inv_total):
        amt = round(inv_total * 0.08, 2)
        return _line(dist, inv, dt, f"Q3 PROMO ALLOW {rng.randint(100,999)}", "PROMO",
                     -amt, "TRADE_PROMO", "valid_trade_spend")

    def easy_scan(dist, inv, dt, inv_total):
        amt = round(inv_total * 0.03, 2)
        return _line(dist, inv, dt, f"SCAN BILLBACK #{rng.randint(10000,99999)}", "SCAN",
                     -amt, "SCAN_ALLOWANCE", "valid_trade_spend")

    def easy_slotting(dist, inv, dt):
        return _line(dist, inv, dt, "SLOTTING Q3 INSTALLMENT", "SLOT",
                     -1500.0, "SLOTTING", "already_accrued")

    def easy_coop(dist, inv, dt, inv_total):
        amt = round(inv_total * 0.02, 2)
        return _line(dist, inv, dt, "COOP FLYER AD", "COOP",
                     -amt, "COOP_ADVERTISING", "valid_trade_spend")

    def easy_accrued_promo(dist, inv, dt):
        return _line(dist, inv, dt, "PROMO ACCRUAL TRUE-UP JUL", "PROMO",
                     -1840.0, "TRADE_PROMO", "already_accrued")

    easy_fns = [easy_trade_promo, easy_scan, easy_coop]

    n_docs = 18
    for i in range(n_docs):
        dist = DIST_UNFI if i % 2 == 0 else DIST_KEHE
        y, m = months[(i // 6) % 3]
        dt = date(y, m, rng.randint(3, 27))
        # NOTE: 25000 (not 23000): 8% of 23000 = 1840 = ACC-001 and
        # 3% of 23000 = 690 = ACC-004, which would make every easy line on
        # such invoices falsely match an open accrual. Invoice menu avoids
        # exact formula/accrual collisions by construction.
        inv_total = float(rng.choice([12000, 16000, 20000, 25000, 28000, 32000]))
        inv = f"INV-{y}{m:02d}-{i + 1:03d}"
        n_lines = rng.randint(5, 8)
        lines = []
        for _ in range(n_lines):
            fn = rng.choice(easy_fns)
            if fn is easy_trade_promo:
                lines.append(fn(dist, inv, dt, inv_total))
            elif fn is easy_scan:
                lines.append(fn(dist, inv, dt, inv_total))
            else:
                lines.append(fn(dist, inv, dt, inv_total))
        # sprinkle one accrued line into ~1/3 of docs
        if i % 3 == 0:
            lines.append(easy_accrued_promo(dist, inv, dt))
        elif i % 3 == 1:
            lines.append(easy_slotting(dist, inv, dt))
        remittances.append(_rem(f"REM-{y}{m:02d}-{i + 1:03d}", dist, dt, inv_total, lines))

    # ---- injected hard cases (each appended to a specific doc so totals stay tied)
    hard = []

    # H1: duplicate deduction — same shortage billed twice (2nd is the duplicate)
    h1a = _line(DIST_UNFI, "INV-DUP-01", date(2026, 7, 9), "SHORTAGE CLAIM TRLR 4471",
                "SHORT", -480.0, "SHORTAGE_CLAIM", "disputable")
    h1b = _line(DIST_UNFI, "INV-DUP-01", date(2026, 7, 22), "SHORTAGE CLAIM TRLR 4471 REBILL",
                "SHORT", -480.0, "SHORTAGE_CLAIM", "disputable",
                lid=h1a["line_id"] + "-DUP")
    # fix dup id bookkeeping (unique id, gt points at duplicate)
    hard += [h1a, h1b]

    # H2: shortage with no matching shipment
    h2 = _line(DIST_KEHE, "INV-SH-902", date(2026, 7, 15), "SHORTAGE CTNS 212 VS 240",
               "SHORT", -1275.0, "SHORTAGE_CLAIM", "disputable")
    hard.append(h2)

    # H3: ADMIN_FEE stacked on out-of-window compliance chargeback
    h3a = _line(DIST_UNFI, "INV-CB-118", date(2026, 8, 4), "CHG-BK LATE ASN MAY SHIP (OUT OF WINDOW)",
                "CHGBK", -350.0, "COMPLIANCE_CHARGEBACK", "disputable")
    h3b = _line(DIST_UNFI, "INV-CB-118", date(2026, 8, 4), "ADMIN FEE CHG-BK 118",
                "ADMFEE", -85.0, "ADMIN_FEE", "disputable")
    hard += [h3a, h3b]

    # H4: cryptic shorthand
    h4a = _line(DIST_KEHE, "INV-CRY-07", date(2026, 8, 11), "SB-ALLOW Q3 ADJ",
                "SB-ALLOW", -412.0, "SCAN_ALLOWANCE", "valid_trade_spend")
    h4b = _line(DIST_UNFI, "INV-CRY-12", date(2026, 8, 12), "CHG-BK REF 88213",
                "CHGBK", -689.0, "COMPLIANCE_CHARGEBACK", "disputable")
    hard += [h4a, h4b]

    # H5: reason_code_raw = None (must go UNKNOWN -> needs_review)
    h5a = _line(DIST_KEHE, "INV-UNK-31", date(2026, 8, 18), "MISC DEDUCT ???",
                None, -233.0, "UNKNOWN", "needs_review")
    h5b = _line(DIST_UNFI, "INV-UNK-44", date(2026, 8, 19), "ADJ - SEE BACKUP",
                None, -517.0, "UNKNOWN", "needs_review")
    hard += [h5a, h5b]

    # H6: spoilage + extra compliance (disputable volume)
    h6a = _line(DIST_KEHE, "INV-SP-55", date(2026, 6, 21), "SPOILAGE EXPIRED 06/25",
                "SPOIL", -940.0, "SPOILAGE_DAMAGE", "disputable")
    h6b = _line(DIST_UNFI, "INV-CB-77", date(2026, 6, 25), "MISLABEL FEE PALLET 9",
                "CHGBK", -150.0, "COMPLIANCE_CHARGEBACK", "disputable")
    hard += [h6a, h6b]

    # distribute hard cases across docs 0..5, re-tie totals
    for k, h in enumerate(hard):
        target = remittances[k % 6]
        target["lines"].append(h)
        inv_total = target["invoice_total"]
        deducted = round(sum(abs(float(l["amount"])) for l in target["lines"]), 2)
        target["cash_received"] = round(inv_total - deducted, 2)

    return {"agreement": agreement, "accruals": accruals, "remittances": remittances,
            "ground_truth": _gt}


def main() -> None:
    import json as _j
    cfg = _j.loads((ROOT / "config.json").read_text())
    out = generate(seed=cfg.get("seed", 42))
    DATA.mkdir(exist_ok=True)
    REMIT_DIR.mkdir(exist_ok=True)
    (DATA / "agreement.json").write_text(_j.dumps(out["agreement"], indent=2))
    (DATA / "accruals.json").write_text(_j.dumps(out["accruals"], indent=2))
    for r in out["remittances"]:
        (REMIT_DIR / f"{r['remittance_id']}.json").write_text(_j.dumps(r, indent=2))
    (DATA / "ground_truth.json").write_text(_j.dumps(out["ground_truth"], indent=2))
    print(f"generated {len(out['remittances'])} remittances, "
          f"{sum(len(r['lines']) for r in out['remittances'])} lines -> data/")


if __name__ == "__main__":
    main()
