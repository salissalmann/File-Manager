"""Tests for the veto rules engine."""

from datetime import date
from decimal import Decimal

import pytest

from src.engine.scorer import score_pair
from src.engine.veto import apply_veto_rules
from src.models import FileRecord, LedgerRow, ScoredCandidate


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


def _score_and_veto(ledger, file):
    candidate = score_pair(ledger, file)
    return apply_veto_rules(ledger, candidate)


class TestCAVeto:
    def test_ca_mismatch_vetoes(self):
        """File has CA 99999, ledger expects 50408 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="WESTHEIMER PLUMBING", ca="50408", amount="17000"),
            _make_file(
                vendor_tokens=["westheimer", "plumbing"],
                ca_codes=["99999"],
                amounts=["17000"],
            ),
        )
        assert c.vetoed is True
        assert "CA mismatch" in c.veto_reason

    def test_ca_absent_no_veto(self):
        """File has NO CA code → no veto (absence is neutral)."""
        c = _score_and_veto(
            _make_ledger(ca="50408", amount="222.77"),
            _make_file(amounts=["222.77"]),
        )
        assert c.vetoed is False

    def test_ca_match_no_veto(self):
        """File has matching CA → no veto."""
        c = _score_and_veto(
            _make_ledger(ca="60110", amount="4520"),
            _make_file(ca_codes=["60110"], amounts=["4520"]),
        )
        assert c.vetoed is False

    def test_wrongca_file_for_row1(self):
        """F26 (ca99999 $17000 westheimer) for Row 1 (ca50408) → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="WESTHEIMER PLUMBING", ca="50408", amount="17000"),
            _make_file(
                vendor_tokens=["westheimer", "plumbing"],
                ca_codes=["99999"],
                amounts=["17000"],
            ),
        )
        assert c.vetoed is True

    def test_wrongca_file_for_row18(self):
        """F26 (ca99999 $17000 westheimer) for Row 18 (ca99999) → NO veto (CA matches)."""
        c = _score_and_veto(
            _make_ledger(vendor="WESTHEIMER PLUMBING", ca="99999", amount="17000"),
            _make_file(
                vendor_tokens=["westheimer", "plumbing"],
                ca_codes=["99999"],
                amounts=["17000"],
            ),
        )
        assert c.vetoed is False


class TestAmountVeto:
    def test_amount_conflict_vetoes(self):
        """File has $9999, ledger expects $99.99 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="Ferguson", ca="60110", amount="99.99"),
            _make_file(
                vendor_tokens=["ferguson"],
                ca_codes=["60110"],
                amounts=["9999"],
            ),
        )
        assert c.vetoed is True
        assert "Amount conflict" in c.veto_reason

    def test_amount_absent_no_veto(self):
        """File has NO amount → no veto."""
        c = _score_and_veto(
            _make_ledger(vendor="Marin Construction", ca="51070", amount="5600"),
            _make_file(vendor_tokens=["marin", "construction"], ca_codes=["51070"]),
        )
        assert c.vetoed is False

    def test_near_amount_no_veto(self):
        """$445.04 vs $445.06 — within tolerance → no veto."""
        c = _score_and_veto(
            _make_ledger(amount="445.04"),
            _make_file(amounts=["445.06"]),
        )
        assert c.vetoed is False

    def test_wrongamount_file(self):
        """F29 (ferguson ca60110 $9999) for Ferguson $4520 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="Ferguson", ca="60110", amount="4520"),
            _make_file(
                vendor_tokens=["ferguson"],
                ca_codes=["60110"],
                amounts=["9999"],
            ),
        )
        assert c.vetoed is True

    def test_260_vs_2260_vetoes(self):
        """$260 vs $2260 — too far apart → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="Ferguson", ca="60110", amount="260"),
            _make_file(
                vendor_tokens=["ferguson"],
                ca_codes=["60110"],
                amounts=["2260"],
            ),
        )
        assert c.vetoed is True


class TestVendorVeto:
    def test_completely_different_vendor_vetoes(self):
        """File is 'westheimer plumbing', ledger is 'Ferguson' → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="Ferguson", ca="50408", amount="17000"),
            _make_file(
                vendor_tokens=["westheimer", "plumbing"],
                ca_codes=["50408"],
                amounts=["17000"],
            ),
        )
        assert c.vetoed is True
        assert "Vendor mismatch" in c.veto_reason

    def test_similar_vendor_no_veto(self):
        """'THE HOME DEPOT' vs 'home depot' → no veto."""
        c = _score_and_veto(
            _make_ledger(vendor="THE HOME DEPOT", amount="222.77"),
            _make_file(vendor_tokens=["home", "depot"], amounts=["222.77"]),
        )
        assert c.vetoed is False

    def test_no_vendor_in_file_no_veto(self):
        """File has no vendor tokens → no veto."""
        c = _score_and_veto(
            _make_ledger(vendor="Ferguson"),
            _make_file(),
        )
        assert c.vetoed is False


class TestMultiAmountVeto:
    def test_multi_amount_one_matches_no_veto(self):
        """File has $17000 and $8500, ledger wants $17000 → no veto."""
        c = _score_and_veto(
            _make_ledger(amount="17000"),
            _make_file(amounts=["17000", "8500"]),
        )
        assert c.vetoed is False

    def test_multi_amount_none_matches_vetoes(self):
        """File has $4520 and $2260, ledger wants $260 → VETO."""
        c = _score_and_veto(
            _make_ledger(amount="260"),
            _make_file(amounts=["4520", "2260"]),
        )
        assert c.vetoed is True
