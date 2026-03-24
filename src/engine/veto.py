"""Veto rules engine — rejects matches even if score is high.

Key principle: absence of data is neutral; presence of WRONG data is a veto.
"""

from __future__ import annotations

from decimal import Decimal

import config
from src.engine.scorer import get_vendor_similarity
from src.models import FileRecord, LedgerRow, ScoredCandidate


def apply_veto_rules(
    ledger_row: LedgerRow, candidate: ScoredCandidate
) -> ScoredCandidate:
    """Apply veto rules to a scored candidate. Sets vetoed=True and veto_reason if rejected."""
    file = candidate.file

    # --- Veto 1: CA mismatch ---
    # File has CA code(s) but NONE match the ledger CA
    if file.ca_codes and ledger_row.ca_code:
        if ledger_row.ca_code not in file.ca_codes:
            candidate.vetoed = True
            candidate.veto_reason = (
                f"CA mismatch: file has {file.ca_codes}, "
                f"ledger expects {ledger_row.ca_code}"
            )
            return candidate

    # --- Veto 2: Amount conflict ---
    # File has amount(s) but NONE are within tolerance of ledger amount
    if file.amounts and ledger_row.amount is not None:
        has_matching_amount = False
        for fa in file.amounts:
            diff = abs(fa - ledger_row.amount)
            abs_ok = diff <= config.AMOUNT_ABS_TOLERANCE
            rel_ok = (
                ledger_row.amount > 0
                and (diff / ledger_row.amount) <= config.AMOUNT_REL_TOLERANCE
            )
            if abs_ok or rel_ok or fa == ledger_row.amount:
                has_matching_amount = True
                break

        if not has_matching_amount:
            candidate.vetoed = True
            candidate.veto_reason = (
                f"Amount conflict: file has {[str(a) for a in file.amounts]}, "
                f"ledger expects {ledger_row.amount}"
            )
            return candidate

    # --- Veto 3: Vendor mismatch ---
    # File clearly belongs to a different vendor
    if file.vendor_tokens:
        similarity = get_vendor_similarity(ledger_row.vendor, file.vendor_tokens)
        if similarity < config.VENDOR_VETO_THRESHOLD:
            candidate.vetoed = True
            candidate.veto_reason = (
                f"Vendor mismatch: file vendor '{file.vendor_name}' vs "
                f"ledger vendor '{ledger_row.vendor}' (similarity: {similarity:.0f}%)"
            )
            return candidate

    return candidate
