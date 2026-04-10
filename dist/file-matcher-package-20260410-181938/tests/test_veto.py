"""Tests for the veto rules engine — uses real vendor names and amounts."""

from datetime import date
from decimal import Decimal

import pytest

from src.engine.scorer import score_pair
from src.engine.veto import apply_veto_rules
from src.models import FileRecord, LedgerRow, ScoredCandidate


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


def _score_and_veto(ledger, file):
    candidate = score_pair(ledger, file)
    return apply_veto_rules(ledger, candidate)


class TestCAVeto:
    def test_ca_mismatch_vetoes(self):
        """File has CA 65100, ledger expects 50670 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="HBIS", ca="50670", amount="4000"),
            _make_file(
                vendor_tokens=["hbis"],
                ca_codes=["65100"],
                amounts=["4000"],
            ),
        )
        assert c.vetoed is True
        assert "CA mismatch" in c.veto_reason

    def test_ca_absent_no_veto(self):
        """File has NO CA code → no veto (absence is neutral). Ledger has no vendor name."""
        c = _score_and_veto(
            _make_ledger(vendor="", ca="50408", amount="222.77"),
            _make_file(amounts=["222.77"]),
        )
        assert c.vetoed is False

    def test_ca_match_no_veto(self):
        """File has matching CA → no veto (ledger vendor blank so file need not name vendor)."""
        c = _score_and_veto(
            _make_ledger(vendor="", ca="50405", amount="17930"),
            _make_file(ca_codes=["50405"], amounts=["17930"]),
        )
        assert c.vetoed is False

    def test_hbis_ca_mismatch(self):
        """HBIS CA 50670 vs file with CA 65100 → VETO (real scenario)."""
        c = _score_and_veto(
            _make_ledger(vendor="HBIS", ca="50670", amount="4000"),
            _make_file(
                vendor_tokens=["hbis"],
                ca_codes=["65100"],
                amounts=["4000"],
            ),
        )
        assert c.vetoed is True

    def test_hbis_ca_match_no_veto(self):
        """HBIS CA 50670 vs file with CA 50670 → NO veto."""
        c = _score_and_veto(
            _make_ledger(vendor="HBIS", ca="50670", amount="4000"),
            _make_file(
                vendor_tokens=["hbis"],
                ca_codes=["50670"],
                amounts=["4000"],
            ),
        )
        assert c.vetoed is False


class TestAmountVeto:
    def test_amount_conflict_vetoes(self):
        """File has $6.08, ledger expects $208.89 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="POT-O-GOLD", ca="50500", amount="208.89"),
            _make_file(
                vendor_tokens=["pot-o-gold"],
                ca_codes=["50500"],
                amounts=["6.08"],
            ),
        )
        assert c.vetoed is True
        assert "Amount conflict" in c.veto_reason

    def test_amount_absent_no_veto(self):
        """File has NO amount → no veto."""
        c = _score_and_veto(
            _make_ledger(vendor="LINC PLUMBING", ca="53608", amount="11566"),
            _make_file(vendor_tokens=["linc", "plumbing"], ca_codes=["53608"]),
        )
        assert c.vetoed is False

    def test_near_amount_now_vetoes(self):
        """$447.50 vs $448 — $0.50 diff exceeds $0.01 abs tolerance → VETO."""
        c = _score_and_veto(
            _make_ledger(amount="447.50"),
            _make_file(amounts=["448"]),
        )
        assert c.vetoed is True
        assert "Amount conflict" in c.veto_reason

    def test_large_amount_mismatch(self):
        """$17930 vs $9999 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="VYO STRUCTURAL", ca="50405", amount="17930"),
            _make_file(
                vendor_tokens=["vyo"],
                ca_codes=["50405"],
                amounts=["9999"],
            ),
        )
        assert c.vetoed is True

    def test_208_vs_6_vetoes(self):
        """$208.89 vs $6.08 — too far apart → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="POT-O-GOLD", ca="50500", amount="208.89"),
            _make_file(
                vendor_tokens=["pot-o-gold"],
                ca_codes=["50500"],
                amounts=["6.08"],
            ),
        )
        assert c.vetoed is True


class TestVendorVeto:
    def test_completely_different_vendor_vetoes(self):
        """File is 'linc plumbing', ledger is 'Deluxe' → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="Deluxe", ca="65100", amount="394.55"),
            _make_file(
                vendor_tokens=["linc", "plumbing"],
                ca_codes=["65100"],
                amounts=["394.55"],
            ),
        )
        assert c.vetoed is True
        assert "Vendor mismatch" in c.veto_reason

    def test_similar_vendor_no_veto(self):
        """'HOME DEPOT' vs 'home depot' → no veto."""
        c = _score_and_veto(
            _make_ledger(vendor="HOME DEPOT", amount="222.77"),
            _make_file(vendor_tokens=["home", "depot"], amounts=["222.77"]),
        )
        assert c.vetoed is False

    def test_no_vendor_in_file_vetoes_when_ledger_names_vendor(self):
        """Ledger names a vendor but filename has no vendor tokens → veto."""
        c = _score_and_veto(
            _make_ledger(vendor="MESKEN"),
            _make_file(),
        )
        assert c.vetoed is True
        assert "No vendor text parsed from filename" in (c.veto_reason or "")

    def test_no_vendor_in_file_ok_when_ledger_vendor_blank(self):
        """No file vendor is allowed if the ledger row has no vendor name."""
        c = _score_and_veto(
            _make_ledger(vendor="", ca="66800", amount="3000"),
            _make_file(ca_codes=["66800"], amounts=["3000"]),
        )
        assert c.vetoed is False


class TestMultiAmountVeto:
    def test_multi_amount_one_matches_no_veto(self):
        """File has $4000+$2850+$3, ledger wants $4000 → no veto (no ledger vendor)."""
        c = _score_and_veto(
            _make_ledger(vendor="", amount="4000"),
            _make_file(amounts=["4000", "2850", "3"]),
        )
        assert c.vetoed is False

    def test_multi_amount_none_matches_vetoes(self):
        """File has $17930 and $7000, ledger wants $208.89 → VETO."""
        c = _score_and_veto(
            _make_ledger(vendor="", amount="208.89"),
            _make_file(amounts=["17930", "7000"]),
        )
        assert c.vetoed is True


class TestAmountVetoBoundary:
    """Boundary tests for amount veto tolerance."""

    def test_amount_diff_one_dollar_vetoes(self):
        """$1345 vs $1346 — $1.00 diff exceeds $0.01 abs tolerance → VETO."""
        c = _score_and_veto(
            _make_ledger(amount="1345"),
            _make_file(amounts=["1346"]),
        )
        assert c.vetoed is True
        assert "Amount conflict" in (c.veto_reason or "")

    def test_amount_diff_over_one_dollar_vetoes(self):
        """1346.02 vs 1345 is $1.02 → reject."""
        c = _score_and_veto(
            _make_ledger(amount="1345"),
            _make_file(amounts=["1346.02"]),
        )
        assert c.vetoed is True
        assert "Amount conflict" in (c.veto_reason or "")

    def test_amount_far_off_veto(self):
        c = _score_and_veto(
            _make_ledger(amount="100"),
            _make_file(amounts=["200"]),
        )
        assert c.vetoed is True

    def test_multi_amount_one_match_several_wrong_no_veto(self):
        c = _score_and_veto(
            _make_ledger(vendor="", amount="3000"),
            _make_file(amounts=["5555", "9999", "3000", "7777"]),
        )
        assert c.vetoed is False


class TestAbsenceIsNeutral:
    """Absence of data in file should never trigger a veto."""

    def test_no_amounts_in_file_no_veto(self):
        c = _score_and_veto(
            _make_ledger(vendor="MESKEN", ca="66800", amount="3000"),
            _make_file(vendor_tokens=["mesken"], ca_codes=["66800"]),
        )
        assert c.vetoed is False

    def test_no_ca_in_file_no_veto(self):
        c = _score_and_veto(
            _make_ledger(vendor="MESKEN", ca="66800", amount="3000"),
            _make_file(vendor_tokens=["mesken"], amounts=["3000"]),
        )
        assert c.vetoed is False

    def test_no_vendor_in_file_vetoes_when_ledger_has_vendor(self):
        c = _score_and_veto(
            _make_ledger(vendor="MESKEN", ca="66800", amount="3000"),
            _make_file(ca_codes=["66800"], amounts=["3000"]),
        )
        assert c.vetoed is True
        assert "No vendor text parsed from filename" in (c.veto_reason or "")


class TestVendorVetoThreshold:
    """Boundary tests for the vendor similarity veto threshold (default 65)."""

    def test_similarity_exactly_65_no_veto(self):
        """Similarity at threshold (65) should not veto."""
        from unittest.mock import patch
        ledger = _make_ledger(vendor="MESKEN")
        file = _make_file(vendor_tokens=["some", "other"])

        with patch("src.engine.veto.get_vendor_similarity", return_value=65.0):
            c = _score_and_veto(ledger, file)
            assert c.vetoed is False

    def test_similarity_64_veto(self):
        """Similarity just below threshold (64) should veto."""
        from unittest.mock import patch
        ledger = _make_ledger(vendor="MESKEN")
        file = _make_file(vendor_tokens=["some", "other"])

        with patch("src.engine.veto.get_vendor_similarity", return_value=64.0):
            c = _score_and_veto(ledger, file)
            assert c.vetoed is True
            assert "Vendor mismatch" in c.veto_reason
