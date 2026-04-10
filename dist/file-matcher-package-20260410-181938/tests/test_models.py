"""Unit tests for MatchResult model properties."""

from datetime import date
from decimal import Decimal

import pytest

from src.models import LedgerRow, MatchResult


def _lr():
    return LedgerRow(index=1, vendor="Deluxe", date=date(2021, 11, 19),
                     ca_code="65100", folder=None, amount=Decimal("394.55"))


class TestMatchResultProperties:
    def test_signal_count_deduplicates_amount(self):
        """Both amount_exact + amount_near counts as 1 signal."""
        r = MatchResult(ledger_row=_lr(), matched_file=None, score=100,
                        reasons=["amount_exact", "amount_near", "ca_match"])
        assert r.signal_count == 2  # (exact/near) + ca

    def test_signal_count_deduplicates_vendor(self):
        """Both vendor_match + vendor_partial counts as 1 signal."""
        r = MatchResult(ledger_row=_lr(), matched_file=None, score=50,
                        reasons=["vendor_match", "vendor_partial"])
        assert r.signal_count == 1

    def test_signal_count_empty(self):
        r = MatchResult(ledger_row=_lr(), matched_file=None, score=0, reasons=[])
        assert r.signal_count == 0

    def test_signal_count_all_three(self):
        r = MatchResult(ledger_row=_lr(), matched_file=None, score=100,
                        reasons=["amount_exact", "ca_match", "vendor_match"])
        assert r.signal_count == 3

    def test_match_reason_str_empty(self):
        r = MatchResult(ledger_row=_lr(), matched_file=None, score=0, reasons=[])
        assert r.match_reason_str == "No signals matched"

    def test_match_reason_str_single(self):
        r = MatchResult(ledger_row=_lr(), matched_file=None, score=50, reasons=["ca_match"])
        assert r.match_reason_str == "ca_match"

    def test_confidence_scale(self):
        r100 = MatchResult(ledger_row=_lr(), matched_file=None, score=100.0)
        assert r100.confidence == 1.0

        r0 = MatchResult(ledger_row=_lr(), matched_file=None, score=0.0)
        assert r0.confidence == 0.0

        r50 = MatchResult(ledger_row=_lr(), matched_file=None, score=50.0)
        assert r50.confidence == 0.5
