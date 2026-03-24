"""Tests for the scoring engine."""

from datetime import date
from decimal import Decimal

import pytest

import config
from src.engine.scorer import score_pair, get_vendor_similarity
from src.models import FileRecord, LedgerRow


def _make_ledger(vendor="Test Vendor", ca="50408", amount="17000"):
    return LedgerRow(
        index=1, vendor=vendor, date=date(2023, 1, 1),
        ca_code=ca, folder=None, amount=Decimal(amount),
    )


def _make_file(vendor_tokens=None, ca_codes=None, amounts=None):
    return FileRecord(
        original_name="test.pdf",
        vendor_tokens=vendor_tokens or [],
        ca_codes=ca_codes or [],
        amounts=[Decimal(a) for a in (amounts or [])],
    )


class TestAmountScoring:
    def test_exact_amount_match(self):
        c = score_pair(_make_ledger(amount="17000"), _make_file(amounts=["17000"]))
        assert c.score >= config.AMOUNT_EXACT_WEIGHT
        assert "amount_exact" in c.reasons

    def test_near_amount_match(self):
        """$445.04 vs $445.06 — within tolerance."""
        c = score_pair(_make_ledger(amount="445.04"), _make_file(amounts=["445.06"]))
        assert c.score >= config.AMOUNT_NEAR_WEIGHT
        assert "amount_near" in c.reasons

    def test_near_amount_1345_vs_1345_50(self):
        """$1345 vs $1345.50 — within tolerance."""
        c = score_pair(_make_ledger(amount="1345"), _make_file(amounts=["1345.50"]))
        assert "amount_near" in c.reasons

    def test_no_amount_in_file(self):
        c = score_pair(_make_ledger(amount="1000"), _make_file(amounts=[]))
        assert "amount_exact" not in c.reasons
        assert "amount_near" not in c.reasons

    def test_wrong_amount_no_score(self):
        """$260 vs $2260 — too far apart."""
        c = score_pair(_make_ledger(amount="260"), _make_file(amounts=["2260"]))
        assert "amount_exact" not in c.reasons
        assert "amount_near" not in c.reasons

    def test_multi_amount_one_matches(self):
        """Multi-amount file: $17000 and $8500 — ledger wants $17000."""
        c = score_pair(_make_ledger(amount="17000"), _make_file(amounts=["17000", "8500"]))
        assert "amount_exact" in c.reasons


class TestCAScoring:
    def test_ca_match(self):
        c = score_pair(_make_ledger(ca="60110"), _make_file(ca_codes=["60110"]))
        assert c.score >= config.CA_MATCH_WEIGHT
        assert "ca_match" in c.reasons

    def test_ca_no_match(self):
        c = score_pair(_make_ledger(ca="50408"), _make_file(ca_codes=["99999"]))
        assert "ca_match" not in c.reasons

    def test_ca_absent_in_file(self):
        """No CA in file = no CA score (neutral, not negative)."""
        c = score_pair(_make_ledger(ca="50408"), _make_file(ca_codes=[]))
        assert "ca_match" not in c.reasons


class TestVendorScoring:
    def test_exact_vendor_match(self):
        c = score_pair(
            _make_ledger(vendor="Ferguson"),
            _make_file(vendor_tokens=["ferguson"]),
        )
        assert "vendor_match" in c.reasons

    def test_the_prefix_handling(self):
        """'THE HOME DEPOT' should match 'home depot'."""
        c = score_pair(
            _make_ledger(vendor="THE HOME DEPOT"),
            _make_file(vendor_tokens=["home", "depot"]),
        )
        assert "vendor_match" in c.reasons

    def test_pot_o_gold_hyphen(self):
        """'Pot-O-Gold' should match 'pot-o-gold'."""
        c = score_pair(
            _make_ledger(vendor="Pot-O-Gold"),
            _make_file(vendor_tokens=["pot-o-gold"]),
        )
        assert "vendor_match" in c.reasons

    def test_completely_different_vendor(self):
        c = score_pair(
            _make_ledger(vendor="Ferguson"),
            _make_file(vendor_tokens=["westheimer", "plumbing"]),
        )
        assert "vendor_match" not in c.reasons
        assert "vendor_partial" not in c.reasons

    def test_no_vendor_in_file(self):
        c = score_pair(
            _make_ledger(vendor="Ferguson"),
            _make_file(vendor_tokens=[]),
        )
        assert "vendor_match" not in c.reasons


class TestCombinedScoring:
    def test_strong_match_all_signals(self):
        """Amount + CA + Vendor = high score."""
        c = score_pair(
            _make_ledger(vendor="Ferguson", ca="60110", amount="4520"),
            _make_file(
                vendor_tokens=["ferguson"],
                ca_codes=["60110"],
                amounts=["4520"],
            ),
        )
        expected_min = (
            config.AMOUNT_EXACT_WEIGHT
            + config.CA_MATCH_WEIGHT
            + config.VENDOR_STRONG_WEIGHT
        )
        assert c.score >= expected_min
        assert "amount_exact" in c.reasons
        assert "ca_match" in c.reasons
        assert "vendor_match" in c.reasons

    def test_medium_match_amount_ca(self):
        """Amount + CA, no vendor."""
        c = score_pair(
            _make_ledger(vendor="Some Vendor", ca="60110", amount="4520"),
            _make_file(ca_codes=["60110"], amounts=["4520"]),
        )
        assert c.score >= config.AMOUNT_EXACT_WEIGHT + config.CA_MATCH_WEIGHT
        assert "vendor_match" not in c.reasons

    def test_weak_match_amount_only(self):
        c = score_pair(
            _make_ledger(vendor="Some Vendor", ca="50408", amount="4520"),
            _make_file(amounts=["4520"]),
        )
        assert c.score >= config.AMOUNT_EXACT_WEIGHT
        assert c.score < config.AMOUNT_EXACT_WEIGHT + config.CA_MATCH_WEIGHT


class TestInvoiceTieBreaker:
    def test_invoice_hint_when_amount_matches(self):
        """Invoice number containing ledger amount as substring gives bonus."""
        ledger = _make_ledger(amount="1199")
        fr = FileRecord(
            original_name="Inv 1199 test.pdf",
            invoice_numbers=["1199"],
        )
        c = score_pair(ledger, fr)
        assert "invoice_hint" in c.reasons
        assert c.score >= config.INVOICE_MATCH_WEIGHT

    def test_no_invoice_hint_when_no_invoices(self):
        """No invoice numbers in file → no bonus."""
        c = score_pair(_make_ledger(amount="1199"), _make_file(amounts=["1199"]))
        assert "invoice_hint" not in c.reasons

    def test_invoice_hint_does_not_trigger_for_non_integer_amount(self):
        """Amount $445.04 is not an integer → no invoice hint."""
        ledger = _make_ledger(amount="445.04")
        fr = FileRecord(
            original_name="Inv 445 test.pdf",
            invoice_numbers=["445"],
        )
        c = score_pair(ledger, fr)
        # 445.04 != int(445.04), so no invoice_hint
        assert "invoice_hint" not in c.reasons


class TestMultiAmountPenalty:
    def test_multi_amount_penalty_applied(self):
        """File with >1 amount gets a penalty."""
        c = score_pair(
            _make_ledger(amount="17000"),
            _make_file(amounts=["17000", "8500"]),
        )
        assert "multi_amount_penalty" in c.reasons
        # Score should be less than exact match alone
        c_single = score_pair(
            _make_ledger(amount="17000"),
            _make_file(amounts=["17000"]),
        )
        assert c.score < c_single.score

    def test_single_amount_no_penalty(self):
        """File with exactly 1 amount gets no penalty."""
        c = score_pair(
            _make_ledger(amount="17000"),
            _make_file(amounts=["17000"]),
        )
        assert "multi_amount_penalty" not in c.reasons


class TestVendorSimilarity:
    def test_high_similarity(self):
        ratio = get_vendor_similarity("Ferguson", ["ferguson"])
        assert ratio >= 85

    def test_low_similarity(self):
        ratio = get_vendor_similarity("Ferguson", ["westheimer", "plumbing"])
        assert ratio < 40

    def test_empty_tokens(self):
        ratio = get_vendor_similarity("Ferguson", [])
        assert ratio == 0.0
