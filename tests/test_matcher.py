"""Tests for the matcher orchestrator."""

from datetime import date
from decimal import Decimal

import pytest

from src.engine.matcher import run_matching
from src.models import LedgerRow


def _lr(index, vendor, ca, amount, dt="2023-01-01"):
    return LedgerRow(
        index=index, vendor=vendor, date=date.fromisoformat(dt),
        ca_code=ca, folder=None, amount=Decimal(str(amount)),
    )


class TestBasicMatching:
    def test_exact_match(self):
        """Single ledger row, single file — exact match."""
        rows = [_lr(1, "Ferguson", "60110", 4520)]
        files = ["6.10.2023 ferguson ca60110 $4520 invoice.pdf"]
        results, orphans = run_matching(rows, files)
        assert len(results) == 1
        assert results[0].matched_file is not None
        assert results[0].status == "Strong"
        assert "amount_exact" in results[0].reasons

    def test_no_match(self):
        """No file matches the ledger row."""
        rows = [_lr(1, "Unknown Vendor", "56000", 1500)]
        files = ["6.10.2023 ferguson ca60110 $4520 invoice.pdf"]
        results, orphans = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert len(orphans) == 1


class TestVetoInMatching:
    def test_ca_mismatch_vetoed(self):
        """File with wrong CA is vetoed, no match assigned."""
        rows = [_lr(1, "WESTHEIMER PLUMBING", "50408", 17000)]
        files = ["3.15.2023 westheimer plumbing ca99999 $17000 wrongca.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is None
        assert results[0].status == "No Match"
        assert len(results[0].vetoed_candidates) > 0

    def test_correct_ca_preferred_over_wrong(self):
        """When one file has correct CA and another has wrong CA, correct one wins."""
        rows = [_lr(1, "WESTHEIMER PLUMBING", "50408", 17000)]
        files = [
            "3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf",
            "3.15.2023 westheimer plumbing ca99999 $17000 wrongca.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert "50408" in results[0].matched_file.ca_codes
        assert results[0].status == "Strong"


class TestOneToOneAssignment:
    def test_duplicate_rows_get_different_files(self):
        """Two identical ledger rows should each get a different file."""
        rows = [
            _lr(1, "ABC Supply", "51010", 5000, "2024-01-01"),
            _lr(2, "ABC Supply", "51010", 5000, "2024-01-01"),
        ]
        files = [
            "1.06.2024 abc supply ca51010 $5000 partial.pdf",
            "1.07.2024 abc supply ca51010 $5000 partial second.pdf",
        ]
        results, orphans = run_matching(rows, files)
        matched_files = {r.matched_file.original_name for r in results if r.matched_file}
        assert len(matched_files) == 2  # Both got different files
        assert len(orphans) == 0

    def test_three_vyo_rows(self):
        """Three VYO rows with $12k, $6k, $6k should each get a file."""
        rows = [
            _lr(1, "VYO Structural", "80100", 12000),
            _lr(2, "VYO Structural", "80100", 6000),
            _lr(3, "VYO Structural", "80100", 6000),
        ]
        files = [
            "4.01.2023 vyo structural ca80100 $12000 framing.pdf",
            "4.02.2023 vyo structural ca80100 $6000 framing part1.pdf",
            "4.03.2023 vyo structural ca80100 $6000 framing part2.pdf",
        ]
        results, orphans = run_matching(rows, files)
        assert results[0].matched_file is not None  # $12k → exact file
        assert results[1].matched_file is not None  # $6k → one of the part files
        assert results[2].matched_file is not None  # $6k → the other part file
        matched_names = {r.matched_file.original_name for r in results}
        assert len(matched_names) == 3


class TestMultiAmountFiles:
    def test_multi_amount_file_matches_two_rows(self):
        """A file with $17000 and $8500 can match two ledger rows."""
        rows = [
            _lr(1, "WESTHEIMER PLUMBING", "50408", 17000),
            _lr(2, "WESTHEIMER PLUMBING", "50408", 8500),
        ]
        files = [
            "3.25.2023 westheimer plumbing ca50408 $17000 and $8500 jb1523.pdf",
        ]
        results, orphans = run_matching(rows, files)
        # Both rows should match the same multi-amount file
        assert results[0].matched_file is not None
        assert results[1].matched_file is not None
        assert results[0].matched_file.original_name == results[1].matched_file.original_name


class TestPartialPaymentSumMatching:
    def test_two_rows_summing_to_file_amount(self):
        """Two unmatched rows whose amounts sum to a file amount should match."""
        rows = [
            _lr(1, "ABC Supply", "51010", 3000),
            _lr(2, "ABC Supply", "51010", 7000),
        ]
        files = [
            "1.05.2024 abc supply ca51010 $10000 project.pdf",
        ]
        results, orphans = run_matching(rows, files)
        # Both rows should be matched to the same file via sum matching
        assert results[0].matched_file is not None
        assert results[1].matched_file is not None
        assert results[0].matched_file.original_name == results[1].matched_file.original_name
        assert "amount_sum_match" in results[0].reasons

    def test_sum_matching_requires_same_vendor_ca(self):
        """Sum matching only triggers for rows with same vendor + CA."""
        rows = [
            _lr(1, "ABC Supply", "51010", 3000),
            _lr(2, "Ferguson", "60110", 7000),  # Different vendor/CA
        ]
        files = [
            "1.05.2024 abc supply ca51010 $10000 project.pdf",
        ]
        results, orphans = run_matching(rows, files)
        # Row 2 shouldn't match — different vendor
        assert results[1].matched_file is None

    def test_sum_matching_only_for_unmatched_rows(self):
        """Sum matching doesn't re-assign rows that already have direct matches."""
        rows = [
            _lr(1, "ABC Supply", "51010", 10000),  # This matches directly
            _lr(2, "ABC Supply", "51010", 3000),    # Unmatched
            _lr(3, "ABC Supply", "51010", 7000),    # Unmatched
        ]
        files = [
            "1.05.2024 abc supply ca51010 $10000 project.pdf",
        ]
        results, orphans = run_matching(rows, files)
        # Row 1 gets the direct match
        assert results[0].matched_file is not None
        assert results[0].status == "Strong"


class TestAlternatives:
    def test_alternatives_populated_for_matches(self):
        """Matched rows should have alternatives list populated."""
        rows = [_lr(1, "WESTHEIMER PLUMBING", "50408", 17000)]
        files = [
            "3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf",
            "3.25.2023 westheimer plumbing ca50408 $17000 and $8500 jb1523.pdf",
        ]
        results, _ = run_matching(rows, files)
        # The winning match should have the other file as an alternative
        assert results[0].matched_file is not None
        assert len(results[0].alternatives) >= 1

    def test_alternatives_limited_to_3(self):
        """Alternatives should be capped at 3 entries."""
        rows = [_lr(1, "ABC Supply", "51010", 5000)]
        files = [
            f"1.0{i}.2024 abc supply ca51010 $5000 partial{i}.pdf"
            for i in range(6)
        ]
        results, _ = run_matching(rows, files)
        assert len(results[0].alternatives) <= 3


class TestEdgeCases:
    def test_vendor_only_match_is_review(self):
        """File with vendor match only (no amount/CA) should be Review."""
        rows = [_lr(1, "Pot-O-Gold", "50500", 250)]
        files = ["pot-o-gold invoice - reprint by invoice"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[0].status == "Review"

    def test_unparseable_file_is_orphan(self):
        """Completely unparseable file should be an orphan."""
        rows = [_lr(1, "Some Vendor", "12345", 100)]
        files = ["20211206_161057"]
        results, orphans = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert len(orphans) == 1
