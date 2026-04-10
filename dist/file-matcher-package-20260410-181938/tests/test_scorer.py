"""Tests for the scoring engine — uses real vendor names, CA codes, and amounts."""

from datetime import date
from decimal import Decimal

import pytest

import config
from src.engine.scorer import score_pair, get_vendor_similarity
from src.models import FileRecord, LedgerRow


def _make_ledger(vendor="Deluxe", ca="65100", amount="394.55"):
    return LedgerRow(
        index=1, vendor=vendor, date=date(2021, 11, 19),
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
        c = score_pair(_make_ledger(amount="17930"), _make_file(amounts=["17930"]))
        assert c.score >= config.AMOUNT_EXACT_WEIGHT
        assert "amount_exact" in c.reasons

    def test_near_amount_match(self):
        """Penny tolerance: $100.00 vs $100.01 counts as near."""
        c = score_pair(_make_ledger(amount="100.00"), _make_file(amounts=["100.01"]))
        assert c.score >= config.AMOUNT_NEAR_WEIGHT
        assert "amount_near" in c.reasons

    def test_near_amount_half_penny(self):
        """$447.505 rounded vs ledger — still within $0.01 if equal after quantize."""
        c = score_pair(_make_ledger(amount="447.50"), _make_file(amounts=["447.51"]))
        assert "amount_near" in c.reasons

    def test_no_amount_in_file(self):
        c = score_pair(_make_ledger(amount="3000"), _make_file(amounts=[]))
        assert "amount_exact" not in c.reasons
        assert "amount_near" not in c.reasons

    def test_wrong_amount_no_score(self):
        """$208.89 vs $6.08 — too far apart."""
        c = score_pair(_make_ledger(amount="208.89"), _make_file(amounts=["6.08"]))
        assert "amount_exact" not in c.reasons
        assert "amount_near" not in c.reasons

    def test_multi_amount_one_matches(self):
        """Multi-amount file: $4000+$2850+$3 — ledger wants $4000."""
        c = score_pair(_make_ledger(amount="4000"), _make_file(amounts=["4000", "2850", "3"]))
        assert "amount_exact" in c.reasons


class TestCAScoring:
    def test_ca_match(self):
        c = score_pair(_make_ledger(ca="50405"), _make_file(ca_codes=["50405"]))
        assert c.score >= config.CA_MATCH_WEIGHT
        assert "ca_match" in c.reasons

    def test_ca_no_match(self):
        c = score_pair(_make_ledger(ca="50670"), _make_file(ca_codes=["65100"]))
        assert "ca_match" not in c.reasons

    def test_ca_absent_in_file(self):
        """No CA in file = no CA score (neutral, not negative)."""
        c = score_pair(_make_ledger(ca="50408"), _make_file(ca_codes=[]))
        assert "ca_match" not in c.reasons


class TestVendorScoring:
    def test_exact_vendor_match(self):
        c = score_pair(
            _make_ledger(vendor="MESKEN"),
            _make_file(vendor_tokens=["mesken"]),
        )
        assert "vendor_match" in c.reasons

    def test_the_prefix_handling(self):
        """'HOME DEPOT' should match 'home depot'."""
        c = score_pair(
            _make_ledger(vendor="HOME DEPOT"),
            _make_file(vendor_tokens=["home", "depot"]),
        )
        assert "vendor_match" in c.reasons

    def test_pot_o_gold_hyphen(self):
        """'POT-O-GOLD' should match 'pot-o-gold'."""
        c = score_pair(
            _make_ledger(vendor="POT-O-GOLD"),
            _make_file(vendor_tokens=["pot-o-gold"]),
        )
        assert "vendor_match" in c.reasons

    def test_completely_different_vendor(self):
        c = score_pair(
            _make_ledger(vendor="MESKEN"),
            _make_file(vendor_tokens=["linc", "plumbing"]),
        )
        assert "vendor_match" not in c.reasons
        assert "vendor_partial" not in c.reasons

    def test_no_vendor_in_file(self):
        c = score_pair(
            _make_ledger(vendor="MESKEN"),
            _make_file(vendor_tokens=[]),
        )
        assert "vendor_match" not in c.reasons

    def test_fuzzy_vendor_total_surveyor(self):
        """'TOTAL SURVEYORS' vs 'total surveyor' (singular) — should score well."""
        ratio = get_vendor_similarity("TOTAL SURVEYORS", ["total", "surveyor"])
        assert ratio >= 70


class TestCombinedScoring:
    def test_strong_match_all_signals(self):
        """Amount + CA + Vendor = high score."""
        c = score_pair(
            _make_ledger(vendor="VYO STRUCTURAL", ca="50405", amount="17930"),
            _make_file(
                vendor_tokens=["vyo"],
                ca_codes=["50405"],
                amounts=["17930"],
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
            _make_ledger(vendor="TACOS CHALES", ca="50405", amount="17930"),
            _make_file(ca_codes=["50405"], amounts=["17930"]),
        )
        assert c.score >= config.AMOUNT_EXACT_WEIGHT + config.CA_MATCH_WEIGHT
        assert "vendor_match" not in c.reasons

    def test_weak_match_amount_only(self):
        c = score_pair(
            _make_ledger(vendor="TACOS CHALES", ca="50670", amount="17930"),
            _make_file(amounts=["17930"]),
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
        """Amount $523.64 is not an integer → no invoice hint."""
        ledger = _make_ledger(amount="523.64")
        fr = FileRecord(
            original_name="Inv 523 test.pdf",
            invoice_numbers=["523"],
        )
        c = score_pair(ledger, fr)
        assert "invoice_hint" not in c.reasons


class TestMultiAmountPenalty:
    def test_multi_amount_penalty_applied(self):
        """File with >1 amount gets a penalty."""
        c = score_pair(
            _make_ledger(amount="4000"),
            _make_file(amounts=["4000", "2850", "3"]),
        )
        assert "multi_amount_penalty" in c.reasons
        c_single = score_pair(
            _make_ledger(amount="4000"),
            _make_file(amounts=["4000"]),
        )
        assert c.score < c_single.score

    def test_single_amount_no_penalty(self):
        """File with exactly 1 amount gets no penalty."""
        c = score_pair(
            _make_ledger(amount="17930"),
            _make_file(amounts=["17930"]),
        )
        assert "multi_amount_penalty" not in c.reasons


class TestVendorSimilarity:
    def test_high_similarity(self):
        ratio = get_vendor_similarity("MESKEN", ["mesken"])
        assert ratio >= 85

    def test_low_similarity(self):
        ratio = get_vendor_similarity("MESKEN", ["linc", "plumbing"])
        assert ratio < 40

    def test_empty_tokens(self):
        ratio = get_vendor_similarity("MESKEN", [])
        assert ratio == 0.0


class TestAmountsWithinTolerance:
    """Direct tests for _amounts_within_tolerance (penny-only)."""

    def test_exact_abs_boundary_pass(self):
        from src.engine.scorer import _amounts_within_tolerance
        assert _amounts_within_tolerance(Decimal("100.01"), Decimal("100.00")) is True

    def test_just_over_penny_fails(self):
        from src.engine.scorer import _amounts_within_tolerance
        assert _amounts_within_tolerance(Decimal("100.02"), Decimal("100.00")) is False

    def test_one_dollar_apart_fails(self):
        from src.engine.scorer import _amounts_within_tolerance
        assert _amounts_within_tolerance(Decimal("201"), Decimal("200")) is False

    def test_two_dollars_apart_fails(self):
        from src.engine.scorer import _amounts_within_tolerance
        assert _amounts_within_tolerance(Decimal("102"), Decimal("100")) is False

    def test_half_dollar_vs_zero_fails(self):
        """$0.50 vs $0.00 exceeds $0.01 abs tolerance → False."""
        from src.engine.scorer import _amounts_within_tolerance
        assert _amounts_within_tolerance(Decimal("0.50"), Decimal("0")) is False

    def test_identical_amounts(self):
        from src.engine.scorer import _amounts_within_tolerance
        assert _amounts_within_tolerance(Decimal("5000"), Decimal("5000")) is True


class TestInvoiceScoreBoundary:
    def test_integer_amount_with_trailing_zero(self):
        ledger = _make_ledger(amount="1000.0")
        fr = FileRecord(original_name="test.pdf", invoice_numbers=["1000"])
        c = score_pair(ledger, fr)
        assert "invoice_hint" in c.reasons

    def test_non_integer_amount_no_trigger(self):
        ledger = _make_ledger(amount="1199.50")
        fr = FileRecord(original_name="test.pdf", invoice_numbers=["1199"])
        c = score_pair(ledger, fr)
        assert "invoice_hint" not in c.reasons

    def test_substring_false_positive(self):
        ledger = _make_ledger(amount="1199")
        fr = FileRecord(original_name="test.pdf", invoice_numbers=["11990"])
        c = score_pair(ledger, fr)
        assert "invoice_hint" in c.reasons


class TestStripPrefix:
    def test_the_prefix(self):
        from src.engine.scorer import _strip_prefix
        assert _strip_prefix("the home depot") == "home depot"

    def test_no_prefix(self):
        from src.engine.scorer import _strip_prefix
        assert _strip_prefix("mesken") == "mesken"

    def test_empty_string(self):
        from src.engine.scorer import _strip_prefix
        assert _strip_prefix("") == ""
