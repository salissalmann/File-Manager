"""Veto rules engine — rejects matches even if score is high.

Key principles:
- Wrong CA / wrong amount / wrong vendor (when filename has vendor text) → veto.
- Ledger names a vendor but filename has no parseable vendor → veto (cannot verify).
- Otherwise absence of CA/amount in the file stays neutral (no veto).
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
    # File has amount(s) but NONE match ledger amount: exact or within
    # AMOUNT_ABS_TOLERANCE (penny). Same rule as scoring — no "near dollar" pairing.
    if file.amounts and ledger_row.amount is not None:
        has_matching_amount = any(
            fa == ledger_row.amount
            or abs(fa - ledger_row.amount) <= config.AMOUNT_ABS_TOLERANCE
            for fa in file.amounts
        )

        if not has_matching_amount:
            candidate.vetoed = True
            candidate.veto_reason = (
                f"Amount conflict: file has {[str(a) for a in file.amounts]}, "
                f"ledger expects {ledger_row.amount}"
            )
            return candidate

    # --- Veto 3: No vendor text in filename ---
    # Ledger expects a named vendor; we cannot fuzzy-check without tokens.
    if ledger_row.vendor and ledger_row.vendor.strip() and not file.vendor_tokens:
        candidate.vetoed = True
        candidate.veto_reason = (
            "No vendor text parsed from filename; cannot verify ledger vendor "
            f"'{ledger_row.vendor}'"
        )
        return candidate

    # --- Veto 4: Vendor mismatch ---
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


def apply_veto_rules_sum_match(
    ledger_row: LedgerRow, candidate: ScoredCandidate
) -> ScoredCandidate:
    """Veto rules for partial-payment sum-match candidates.

    Applies CA and vendor veto rules but skips the amount conflict veto,
    since sum-match rows intentionally have individual amounts that don't
    equal the file amount (they sum to it).
    """
    file = candidate.file

    # --- Veto 1: CA mismatch ---
    if file.ca_codes and ledger_row.ca_code:
        if ledger_row.ca_code not in file.ca_codes:
            candidate.vetoed = True
            candidate.veto_reason = (
                f"CA mismatch: file has {file.ca_codes}, "
                f"ledger expects {ledger_row.ca_code}"
            )
            return candidate

    # --- Veto 2: No vendor text in filename (same as main veto path) ---
    if ledger_row.vendor and ledger_row.vendor.strip() and not file.vendor_tokens:
        candidate.vetoed = True
        candidate.veto_reason = (
            "No vendor text parsed from filename; cannot verify ledger vendor "
            f"'{ledger_row.vendor}'"
        )
        return candidate

    # --- Veto 3: Vendor mismatch (amount conflict skipped for sum-match) ---
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
