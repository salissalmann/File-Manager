"""Generate plain-English explanations for match results."""

from __future__ import annotations

from decimal import Decimal

from src.models import MatchResult


_REASON_LABELS: dict[str, str] = {
    "amount_exact": "exact amount match",
    "amount_near": "near amount match",
    "amount_sum_match": "partial payment sum",
    "ca_match": "CA code confirmed",
    "vendor_match": "vendor matched",
    "vendor_partial": "vendor partially matched",
    "invoice_hint": "invoice number hint",
    "multi_amount_penalty": "multi-amount penalty",
}


def format_reasons(reasons: list[str]) -> str:
    """Map internal reason tokens to plain-English labels."""
    return " + ".join(_REASON_LABELS.get(r, r) for r in reasons)


def explain(result: MatchResult) -> str:
    """Produce a self-contained plain-English explanation for a match result.

    Includes actual values: amounts, CA codes, vendor names.
    Each explanation stands on its own without needing to see code or config.
    """
    if result.status == "No Match":
        return _explain_no_match(result)
    return _explain_match(result)


def explain_ambiguity(result: MatchResult) -> str:
    """Build ambiguity explanation. Returns empty string if not ambiguous."""
    if not result.is_ambiguous:
        return ""
    if not result.alternatives:
        return "AMBIGUOUS: competing candidates exist but details are unavailable."

    parts = [f"AMBIGUOUS: {len(result.alternatives) + 1} competing candidates."]
    parts.append(
        f"  Winner: {result.matched_file.original_name} "
        f"(score={result.score:.0f}, {format_reasons(result.reasons)})"
    )
    for i, alt in enumerate(result.alternatives[:3], start=2):
        parts.append(
            f"  #{i}: {alt.file.original_name} "
            f"(score={alt.score:.0f}, {format_reasons(alt.reasons)})"
        )
    return "\n".join(parts)


def format_signals(result: MatchResult) -> str:
    """Format signal count as '3/3 (amount_exact + ca + vendor)'."""
    reasons = set(result.reasons)
    signals = []

    if reasons & {"amount_exact", "amount_near", "amount_sum_match"}:
        if "amount_exact" in reasons:
            signals.append("amount_exact")
        elif "amount_near" in reasons:
            signals.append("amount_near")
        else:
            signals.append("amount_sum")
    if "ca_match" in reasons:
        signals.append("ca")
    if reasons & {"vendor_match", "vendor_partial"}:
        if "vendor_match" in reasons:
            signals.append("vendor")
        else:
            signals.append("vendor_partial")

    if signals:
        return f"{len(signals)}/3 ({' + '.join(signals)})"
    return "0/3"


def _explain_match(result: MatchResult) -> str:
    """Build explanation for a matched row."""
    parts = []
    row = result.ledger_row
    f = result.matched_file
    reasons = set(result.reasons)

    parts.append(f"{result.status} match")

    # Amount explanation
    if "amount_exact" in reasons:
        parts.append(f"Ledger amount ${row.amount:,} matches file amount exactly")
    elif "amount_near" in reasons:
        file_amt = _closest_amount(row.amount, f.amounts)
        if file_amt is not None:
            diff = abs(row.amount - file_amt)
            parts.append(
                f"Ledger amount ${row.amount:,} is within ${diff} "
                f"of file amount ${file_amt:,}"
            )
        else:
            parts.append(f"Ledger amount ${row.amount:,} is a near-match to file")
    elif "amount_sum_match" in reasons:
        parts.append(
            f"Ledger amount ${row.amount:,} is part of a partial payment sum-match"
        )
    else:
        if f.amounts:
            file_amts = ", ".join(f"${a:,}" for a in f.amounts)
            parts.append(
                f"No amount match (ledger: ${row.amount:,}, file: {file_amts})"
            )
        else:
            parts.append(f"No amount found in file (ledger: ${row.amount:,})")

    # CA explanation
    if "ca_match" in reasons:
        parts.append(f"CA code {row.ca_code} confirmed in file")
    elif f.ca_codes:
        parts.append(
            f"CA code mismatch (ledger: {row.ca_code}, "
            f"file: {', '.join(f.ca_codes)})"
        )
    else:
        parts.append(f"File has no CA code (ledger expects {row.ca_code})")

    # Vendor explanation
    if "vendor_match" in reasons:
        parts.append(
            f"Vendor '{row.vendor}' matches file vendor '{f.vendor_name}'"
        )
    elif "vendor_partial" in reasons:
        parts.append(
            f"Vendor '{row.vendor}' partially matches file vendor '{f.vendor_name}'"
        )
    elif f.vendor_tokens:
        parts.append(
            f"Vendor '{row.vendor}' did not match file vendor '{f.vendor_name}'"
        )
    else:
        parts.append("File has no identifiable vendor name")

    return ". ".join(parts) + "."


def _explain_no_match(result: MatchResult) -> str:
    """Build explanation for an unmatched row."""
    row = result.ledger_row
    base = (
        f"No match found for {row.vendor}, CA {row.ca_code}, "
        f"${row.amount:,}"
    )
    if result.vetoed_candidates:
        vc = result.vetoed_candidates[0]
        base += (
            f". Closest candidate '{vc.file.original_name}' was rejected: "
            f"{vc.veto_reason}"
        )
    return base + "."


def _closest_amount(
    ledger_amount: Decimal, file_amounts: list[Decimal]
) -> Decimal | None:
    """Find the file amount closest to the ledger amount."""
    if not file_amounts:
        return None
    return min(file_amounts, key=lambda fa: abs(fa - ledger_amount))
