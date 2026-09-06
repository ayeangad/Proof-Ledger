"""Parsing layer — load remittances, enforce the reconciliation invariant loudly."""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import Remittance

ROOT = Path(__file__).resolve().parents[1]
REMIT_DIR = ROOT / "data" / "remittances"


class InvariantError(ValueError):
    pass


def check_invariant(rem: Remittance, tol: float = 0.01) -> None:
    expected = rem.invoice_total - rem.cash_received
    actual = sum(abs(float(l.amount)) for l in rem.lines)
    if abs(expected - actual) > tol:
        raise InvariantError(
            f"{rem.remittance_id}: invoice_total - cash_received = {expected:.2f} "
            f"!= sum(line amounts) = {actual:.2f}"
        )


def load_all() -> list[Remittance]:
    rems = []
    for p in sorted(REMIT_DIR.glob("*.json")):
        rem = Remittance(**json.loads(p.read_text()))
        check_invariant(rem)
        rems.append(rem)
    if not rems:
        raise InvariantError("no remittance files found in data/remittances")
    return rems
