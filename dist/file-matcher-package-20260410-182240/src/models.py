"""Data models for the file-to-ledger matching engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class FileRecord:
    """Structured data extracted from an unstructured filename."""

    original_name: str
    dates: list[date] = field(default_factory=list)
    vendor_tokens: list[str] = field(default_factory=list)
    ca_codes: list[str] = field(default_factory=list)  # digits only, "ca" prefix stripped
    amounts: list[Decimal] = field(default_factory=list)
    invoice_numbers: list[str] = field(default_factory=list)
    job_numbers: list[str] = field(default_factory=list)

    @property
    def vendor_name(self) -> str:
        """Reconstructed vendor name from tokens."""
        return " ".join(self.vendor_tokens)


@dataclass
class LedgerRow:
    """A single row from the ledger Excel file."""

    index: int  # 1-based row index in the spreadsheet
    vendor: str
    date: date
    ca_code: str
    folder: str | None
    amount: Decimal


@dataclass
class ScoredCandidate:
    """A file scored against a specific ledger row."""

    file: FileRecord
    score: float  # 0-100
    reasons: list[str] = field(default_factory=list)  # e.g. ["amount_exact", "ca_match"]
    vetoed: bool = False
    veto_reason: str | None = None


@dataclass
class MatchResult:
    """Final match result for one ledger row."""

    ledger_row: LedgerRow
    matched_file: FileRecord | None
    score: float  # 0-100
    reasons: list[str] = field(default_factory=list)
    status: str = "No Match"  # Confident / Probable / Possible / Review / No Match
    vetoed_candidates: list[ScoredCandidate] = field(default_factory=list)
    all_candidates: list[ScoredCandidate] = field(default_factory=list)
    alternatives: list[ScoredCandidate] = field(default_factory=list)  # top 2-3 runner-ups
    is_ambiguous: bool = False

    @property
    def match_reason_str(self) -> str:
        """Human-readable match reason."""
        if not self.reasons:
            return "No signals matched"
        return " + ".join(self.reasons)

    @property
    def confidence(self) -> float:
        """Confidence as a 0.0-1.0 float."""
        return round(self.score / 100.0, 2)

    @property
    def signal_count(self) -> int:
        """Count core signals that fired (amount, CA, vendor). Max 3."""
        reasons = set(self.reasons)
        has_amount = bool(reasons & {"amount_exact", "amount_near", "amount_sum_match"})
        has_ca = "ca_match" in reasons
        has_vendor = bool(reasons & {"vendor_match", "vendor_partial"})
        return sum([has_amount, has_ca, has_vendor])
