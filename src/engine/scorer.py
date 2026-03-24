"""Signal-based scoring engine for ledger-to-file matching."""

from __future__ import annotations

from decimal import Decimal

from rapidfuzz import fuzz

import config
from src.models import FileRecord, LedgerRow, ScoredCandidate


def score_pair(ledger_row: LedgerRow, file_record: FileRecord) -> ScoredCandidate:
    """Score a single (ledger_row, file_record) pair based on matching signals.

    Returns a ScoredCandidate with score (0-100) and list of matched reasons.
    """
    score = 0.0
    reasons: list[str] = []

    # --- Amount signal (highest weight) ---
    amount_result = _score_amount(ledger_row.amount, file_record.amounts)
    score += amount_result[0]
    if amount_result[1]:
        reasons.append(amount_result[1])

    # --- CA code signal ---
    ca_result = _score_ca(ledger_row.ca_code, file_record.ca_codes)
    score += ca_result[0]
    if ca_result[1]:
        reasons.append(ca_result[1])

    # --- Vendor signal ---
    vendor_result = _score_vendor(ledger_row.vendor, file_record.vendor_tokens)
    score += vendor_result[0]
    if vendor_result[1]:
        reasons.append(vendor_result[1])

    # --- Invoice number tie-breaker (small bonus) ---
    inv_result = _score_invoice(ledger_row, file_record)
    score += inv_result[0]
    if inv_result[1]:
        reasons.append(inv_result[1])

    # --- Multi-amount penalty (file has >1 amount = ambiguity) ---
    if len(file_record.amounts) > 1:
        score -= config.MULTI_AMOUNT_PENALTY
        reasons.append("multi_amount_penalty")

    return ScoredCandidate(
        file=file_record,
        score=max(min(score, 100.0), 0.0),
        reasons=reasons,
    )


def _score_amount(
    ledger_amount: Decimal, file_amounts: list[Decimal]
) -> tuple[float, str | None]:
    """Score amount matching. Returns (points, reason_string)."""
    if not file_amounts:
        return 0.0, None

    for fa in file_amounts:
        if fa == ledger_amount:
            return config.AMOUNT_EXACT_WEIGHT, "amount_exact"

    # Check near-match with tolerance
    for fa in file_amounts:
        if _amounts_within_tolerance(fa, ledger_amount):
            return config.AMOUNT_NEAR_WEIGHT, "amount_near"

    return 0.0, None


def _score_ca(ledger_ca: str, file_cas: list[str]) -> tuple[float, str | None]:
    """Score CA code matching. Returns (points, reason_string)."""
    if not file_cas or not ledger_ca:
        return 0.0, None

    if ledger_ca in file_cas:
        return config.CA_MATCH_WEIGHT, "ca_match"

    return 0.0, None


def _score_vendor(
    ledger_vendor: str, file_vendor_tokens: list[str]
) -> tuple[float, str | None]:
    """Score vendor name matching using fuzzy comparison.

    Returns (points, reason_string).
    """
    if not file_vendor_tokens:
        return 0.0, None

    file_vendor_str = " ".join(file_vendor_tokens).lower()
    ledger_lower = ledger_vendor.lower()

    # Strip common prefixes like "THE" for better matching
    ledger_stripped = _strip_prefix(ledger_lower)
    file_stripped = _strip_prefix(file_vendor_str)

    # Use the best of: full match, stripped match, token sort
    ratio = max(
        fuzz.ratio(ledger_lower, file_vendor_str),
        fuzz.ratio(ledger_stripped, file_stripped),
        fuzz.token_sort_ratio(ledger_lower, file_vendor_str),
        fuzz.partial_ratio(ledger_stripped, file_stripped),
    )

    if ratio >= config.VENDOR_STRONG_THRESHOLD:
        return config.VENDOR_STRONG_WEIGHT, "vendor_match"
    if ratio >= config.VENDOR_PARTIAL_THRESHOLD:
        return config.VENDOR_PARTIAL_WEIGHT, "vendor_partial"

    return 0.0, None


def _score_invoice(
    ledger_row: LedgerRow, file_record: FileRecord
) -> tuple[float, str | None]:
    """Score invoice number matching as a tie-breaker.

    Checks if the ledger amount (as integer string) appears in any file
    invoice number — a hint that this file relates to this ledger row.
    """
    if not file_record.invoice_numbers:
        return 0.0, None

    amount_int = int(ledger_row.amount) if ledger_row.amount == int(ledger_row.amount) else None
    if amount_int is not None:
        amount_str = str(amount_int)
        for inv in file_record.invoice_numbers:
            if amount_str in inv:
                return config.INVOICE_MATCH_WEIGHT, "invoice_hint"

    return 0.0, None


def _strip_prefix(name: str) -> str:
    """Strip common vendor name prefixes."""
    prefixes = ("the ", "a ")
    for p in prefixes:
        if name.startswith(p):
            return name[len(p):]
    return name


def get_vendor_similarity(ledger_vendor: str, file_vendor_tokens: list[str]) -> float:
    """Get the fuzzy similarity ratio between vendor names.

    Used by veto logic — intentionally stricter than scoring (no partial_ratio)
    to avoid false negatives on the veto check.
    """
    if not file_vendor_tokens:
        return 0.0

    file_vendor_str = " ".join(file_vendor_tokens).lower()
    ledger_lower = ledger_vendor.lower()
    ledger_stripped = _strip_prefix(ledger_lower)
    file_stripped = _strip_prefix(file_vendor_str)

    return max(
        fuzz.ratio(ledger_lower, file_vendor_str),
        fuzz.ratio(ledger_stripped, file_stripped),
        fuzz.token_sort_ratio(ledger_lower, file_vendor_str),
    )


def _amounts_within_tolerance(a: Decimal, b: Decimal) -> bool:
    """Check if two amounts are within configured tolerance."""
    diff = abs(a - b)
    abs_ok = diff <= config.AMOUNT_ABS_TOLERANCE
    rel_ok = b > 0 and (diff / b) <= config.AMOUNT_REL_TOLERANCE
    return abs_ok or rel_ok
