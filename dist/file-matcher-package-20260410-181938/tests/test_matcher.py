"""Tests for the matcher orchestrator — uses real vendor names and filenames."""

from datetime import date
from decimal import Decimal

import pytest

from src.engine.matcher import run_matching, _is_ambiguous
from src.models import FileRecord, LedgerRow, ScoredCandidate


def _lr(index, vendor, ca, amount, dt="2021-12-01"):
    return LedgerRow(
        index=index, vendor=vendor, date=date.fromisoformat(dt),
        ca_code=ca, folder=None, amount=Decimal(str(amount)),
    )


class TestBasicMatching:
    def test_exact_match_vyo(self):
        """Single ledger row, single file — exact match (VYO real data)."""
        rows = [_lr(1, "VYO STRUCTURAL", "50405", 17930)]
        files = ["12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf"]
        results, orphans = run_matching(rows, files)
        assert len(results) == 1
        assert results[0].matched_file is not None
        assert results[0].status == "Confident"
        assert "amount_exact" in results[0].reasons

    def test_no_match(self):
        """No file matches the ledger row."""
        rows = [_lr(1, "TACOS CHALES", "53604", 132.61)]
        files = ["12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf"]
        results, orphans = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert len(orphans) == 1


class TestVetoInMatching:
    def test_ca_mismatch_vetoed(self):
        """HBIS file with CA 65100 vetoed when ledger expects CA 50670."""
        rows = [_lr(1, "HBIS", "50670", 4000)]
        files = ["12.09.2021 HBIS Ck 1000 Ca 65100 Builders Risk Jb 1523 MIlford $4000.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is None
        assert results[0].status == "No Match"
        assert len(results[0].vetoed_candidates) > 0

    def test_correct_ca_preferred_over_wrong(self):
        """When one file has correct CA and another has wrong CA, correct one wins."""
        rows = [_lr(1, "HBIS", "50670", 4000)]
        files = [
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000.pdf",
            "12.09.2021 HBIS Ck 1000 Ca 65100 Builders Risk Jb 1523 MIlford $4000.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert "50670" in results[0].matched_file.ca_codes
        assert results[0].status == "Confident"


class TestOneToOneAssignment:
    def test_duplicate_rows_get_different_files(self):
        """Two identical ledger rows should each get a different file."""
        rows = [
            _lr(1, "MESKEN", "66800", 3000, "2022-01-01"),
            _lr(2, "MESKEN", "66800", 3000, "2022-01-01"),
        ]
        files = [
            "1.21.2022 mesken Ca 66800 $3000 jb 1523 Milford.pdf",
            "2.15.2022 mesken Ca 66800 $3000 jb 1523 Milford.pdf",
        ]
        results, orphans = run_matching(rows, files)
        matched_files = {r.matched_file.original_name for r in results if r.matched_file}
        assert len(matched_files) == 2
        assert len(orphans) == 0

    def test_three_vyo_rows(self):
        """Three VYO rows with different amounts should each get a file."""
        rows = [
            _lr(1, "VYO STRUCTURAL", "50405", 17930),
            _lr(2, "VYO STRUCTURAL", "50405", 6000),
            _lr(3, "VYO STRUCTURAL", "50405", 6000),
        ]
        files = [
            "12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf",
            "1.05.2022 VYO CA 50405 $6000 part1.pdf",
            "1.06.2022 VYO CA 50405 $6000 part2.pdf",
        ]
        results, orphans = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[1].matched_file is not None
        assert results[2].matched_file is not None
        matched_names = {r.matched_file.original_name for r in results}
        assert len(matched_names) == 3


class TestMultiAmountFiles:
    def test_multi_amount_file_matches_two_rows(self):
        """HBIS file with $4000+$2850+$3 can match two ledger rows."""
        rows = [
            _lr(1, "HBIS", "50670", 4000),
            _lr(2, "HBIS", "50670", 2850),
        ]
        files = [
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000+$2850+$3.pdf",
        ]
        results, orphans = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[1].matched_file is not None
        assert results[0].matched_file.original_name == results[1].matched_file.original_name


class TestPartialPaymentSumMatching:
    def test_two_rows_summing_to_file_amount(self):
        """Two unmatched rows whose amounts sum to a file amount should match."""
        rows = [
            _lr(1, "MESKEN", "66800", 3000),
            _lr(2, "MESKEN", "66800", 7000),
        ]
        files = [
            "1.21.2022 mesken Ca 66800 $10000 jb 1523 Milford.pdf",
        ]
        results, orphans = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[1].matched_file is not None
        assert results[0].matched_file.original_name == results[1].matched_file.original_name
        assert "amount_sum_match" in results[0].reasons

    def test_sum_matching_requires_same_vendor_ca(self):
        """Sum matching only triggers for rows with same vendor + CA."""
        rows = [
            _lr(1, "MESKEN", "66800", 3000),
            _lr(2, "LINC PLUMBING", "53608", 7000),
        ]
        files = [
            "1.21.2022 mesken Ca 66800 $10000 jb 1523 Milford.pdf",
        ]
        results, orphans = run_matching(rows, files)
        assert results[1].matched_file is None

    def test_sum_matching_only_for_unmatched_rows(self):
        """Sum matching doesn't re-assign rows that already have direct matches."""
        rows = [
            _lr(1, "MESKEN", "66800", 10000),
            _lr(2, "MESKEN", "66800", 3000),
            _lr(3, "MESKEN", "66800", 7000),
        ]
        files = [
            "1.21.2022 mesken Ca 66800 $10000 jb 1523 Milford.pdf",
        ]
        results, orphans = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[0].status == "Confident"


class TestAlternatives:
    def test_alternatives_populated_for_matches(self):
        """Matched rows should have alternatives list populated."""
        rows = [_lr(1, "HBIS", "50670", 4000)]
        files = [
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000.pdf",
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000+$2850+$3.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert len(results[0].alternatives) >= 1

    def test_alternatives_limited_to_3(self):
        """Alternatives should be capped at 3 entries."""
        rows = [_lr(1, "MESKEN", "66800", 3000)]
        files = [
            f"1.{i:02d}.2022 mesken Ca 66800 $3000 jb 1523 Milford.pdf"
            for i in range(6)
        ]
        results, _ = run_matching(rows, files)
        assert len(results[0].alternatives) <= 3


class TestEdgeCases:
    def test_vendor_only_match_is_review(self):
        """File with vendor match only (no amount/CA) should be Review."""
        rows = [_lr(1, "POT-O-GOLD", "50500", 208.89)]
        files = ["pot-o-gold invoice - reprint by invoice.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[0].status == "Review"

    def test_unparseable_file_is_orphan(self):
        """Completely unparseable file should be an orphan."""
        rows = [_lr(1, "TACOS CHALES", "53604", 132.61)]
        files = ["20211206_161057"]
        results, orphans = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert len(orphans) == 1


class TestFiveTierClassification:
    """Tests for the 5-tier signal-count classification."""

    def test_three_signals_not_ambiguous_is_confident(self):
        """3 signals (amount + CA + vendor), no close competitor → Confident."""
        rows = [_lr(1, "VYO STRUCTURAL", "50405", 17930)]
        files = ["12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "Confident"
        assert results[0].signal_count == 3
        assert not results[0].is_ambiguous

    def test_three_signals_ambiguous_is_probable(self):
        """3 signals but close competitor → Probable."""
        rows = [_lr(1, "HBIS", "50670", 4000)]
        files = [
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000.pdf",
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000+$2850+$3.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert results[0].status == "Probable"
        assert results[0].is_ambiguous

    def test_two_signals_amount_vendor_is_probable(self):
        """2 signals (amount + vendor), no CA → Probable."""
        rows = [_lr(1, "HOME DEPOT", "50408", 222.77)]
        files = ["12.27.2021  the home depost $222.77 jb 1523 milford.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "Probable"
        assert results[0].signal_count == 2

    def test_two_signals_ca_vendor_is_probable(self):
        """2 signals (CA + vendor), no amount → Probable."""
        rows = [_lr(1, "MESKEN", "66800", 3000)]
        files = ["1.21.2022 mesken Ca 66800 jb 1523 Milford.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "Probable"

    def test_vendor_only_capped_at_review(self):
        """Vendor-only match (no amount, no CA) → always Review."""
        rows = [_lr(1, "POT-O-GOLD", "50500", 208.89)]
        files = ["pot-o-gold invoice - reprint by invoice.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "Review"

    def test_sum_match_three_signals_is_possible(self):
        """Sum-match with 3 signals → Possible (not Confident)."""
        rows = [
            _lr(1, "MESKEN", "66800", 3000),
            _lr(2, "MESKEN", "66800", 7000),
        ]
        files = ["1.21.2022 mesken Ca 66800 $10000 jb 1523 Milford.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert "amount_sum_match" in results[0].reasons
        assert results[0].status == "Possible"

    def test_no_signals_is_no_match(self):
        """No matching signals → No Match."""
        rows = [_lr(1, "TACOS CHALES", "53604", 132.61)]
        files = ["20211206_161057"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "No Match"


class TestAmbiguityDetection:
    """Tests for the _is_ambiguous logic."""

    def test_large_gap_not_ambiguous(self):
        """When winner is far ahead, no ambiguity."""
        rows = [_lr(1, "VYO STRUCTURAL", "50405", 17930)]
        files = [
            "12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf",
            "12.10.2021 VYO CA 50405 $6000.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert not results[0].is_ambiguous

    def test_close_competitor_triggers_ambiguity(self):
        """When competitor has similar score + signals → ambiguous."""
        rows = [_lr(1, "HBIS", "50670", 4000)]
        files = [
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000.pdf",
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000+$2850+$3.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert results[0].is_ambiguous
        assert results[0].status == "Probable"

    def test_vetoed_competitor_not_counted(self):
        """Vetoed candidates don't count for ambiguity."""
        rows = [_lr(1, "HBIS", "50670", 4000)]
        files = [
            "12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000.pdf",
            "12.09.2021 HBIS Ck 1000 Ca 65100 Builders Risk Jb 1523 MIlford $4000.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert not results[0].is_ambiguous
        assert results[0].status == "Confident"


class TestAmbiguityThresholdBoundary:
    """Boundary tests for the ambiguity score gap (default gap < 15)."""

    def test_gap_exactly_15_not_ambiguous(self):
        """Winner 100, competitor 85 → gap 15. < 15 is False → NOT ambiguous."""
        winner = ScoredCandidate(
            file=FileRecord(original_name="winner.pdf", vendor_tokens=[], ca_codes=[], amounts=[]),
            score=100.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
        )
        competitor = ScoredCandidate(
            file=FileRecord(original_name="competitor.pdf", vendor_tokens=[], ca_codes=[], amounts=[]),
            score=85.0,
            reasons=["amount_exact", "ca_match"],
        )
        assert _is_ambiguous(winner, [winner, competitor]) is False

    def test_gap_14_is_ambiguous(self):
        """Winner 100, competitor 86 → gap 14. < 15 is True → IS ambiguous."""
        winner = ScoredCandidate(
            file=FileRecord(original_name="winner.pdf", vendor_tokens=[], ca_codes=[], amounts=[]),
            score=100.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
        )
        competitor = ScoredCandidate(
            file=FileRecord(original_name="competitor.pdf", vendor_tokens=[], ca_codes=[], amounts=[]),
            score=86.0,
            reasons=["amount_exact", "ca_match"],
        )
        assert _is_ambiguous(winner, [winner, competitor]) is True

    def test_score_zero_competitor_skipped(self):
        """Competitor with score 0 → skip (even if gap < 15)."""
        winner = ScoredCandidate(
            file=FileRecord(original_name="winner.pdf", vendor_tokens=[], ca_codes=[], amounts=[]),
            score=5.0,
            reasons=["vendor_partial"],
        )
        competitor = ScoredCandidate(
            file=FileRecord(original_name="competitor.pdf", vendor_tokens=[], ca_codes=[], amounts=[]),
            score=0.0,
            reasons=[],
        )
        assert _is_ambiguous(winner, [winner, competitor]) is False


class TestClassificationEdgeCases:
    """Edge cases for tier assignment."""

    def test_ca_only_no_match_when_ledger_names_vendor(self):
        """CA-only in filename but no vendor text → cannot verify ledger vendor → No Match."""
        rows = [_lr(1, "TACOS CHALES", "53604", 132.61)]
        files = ["ca53604.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert results[0].matched_file is None

    def test_amount_exact_only_no_match_when_ledger_names_vendor(self):
        """Exact amount in filename but no vendor text → No Match."""
        rows = [_lr(1, "TACOS CHALES", "53604", 132.61)]
        files = ["$132.61.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert results[0].matched_file is None

    def test_generic_filename_no_match_when_ledger_names_vendor(self):
        """Ring.png parses vendor token 'ring'; veto similarity rejects vs WESTHEIMER."""
        rows = [_lr(1, "WESTHEIMER PLUMBING", "50408", 397.06)]
        files = ["Ring.png"]
        results, _ = run_matching(rows, files)
        assert results[0].status == "No Match"
        assert results[0].matched_file is None

    def test_two_signals_ambiguous_is_possible(self):
        """2 signals but ambiguous → Possible (downgraded from Probable)."""
        rows = [_lr(1, "HOME DEPOT", "50408", 222.77)]
        files = [
            "home depot $222.77.pdf",
            "home depot $222.77 copy.pdf",
        ]
        results, _ = run_matching(rows, files)
        assert results[0].is_ambiguous
        assert results[0].status == "Possible"

    def test_exact_amount_three_signals_not_ambiguous_is_confident(self):
        """Exact-amount + CA + vendor, not ambiguous → Confident."""
        rows = [_lr(1, "TOTAL SURVEYORS", "54500", 447.50)]
        files = ["total surveyors ca54500 $447.50.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].signal_count == 3
        assert not results[0].is_ambiguous
        assert "amount_exact" in results[0].reasons
        assert results[0].status == "Confident"

    def test_near_amount_now_vetoed(self):
        """$447.50 vs $448 exceeds $0.01 tolerance → amount conflict veto → no match."""
        rows = [_lr(1, "TOTAL SURVEYORS", "54500", 447.50)]
        files = ["total surveyors ca54500 $448.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is None


class TestMultiAmountCapacity:
    """Tests for greedy one-to-one assignment capacity."""

    def test_file_with_3_amounts_matches_3_rows(self):
        rows = [
            _lr(1, "HBIS", "50670", 4000),
            _lr(2, "HBIS", "50670", 2850),
            _lr(3, "HBIS", "50670", 3),
        ]
        files = ["12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000+$2850+$3.pdf"]
        results, _ = run_matching(rows, files)
        assert results[0].matched_file is not None
        assert results[1].matched_file is not None
        assert results[2].matched_file is not None
        assert results[0].matched_file.original_name == results[1].matched_file.original_name == results[2].matched_file.original_name

    def test_file_with_0_amounts_max_1_assignment(self):
        """File with 0 amounts (e.g. vendor-only match) can only be assigned once."""
        rows = [
            _lr(1, "POT-O-GOLD", "50500", 208.89),
            _lr(2, "POT-O-GOLD", "50500", 250),
        ]
        files = ["pot-o-gold invoice - reprint by invoice.pdf"]
        results, orphans = run_matching(rows, files)
        matched_count = sum(1 for r in results if r.matched_file is not None)
        assert matched_count == 1
