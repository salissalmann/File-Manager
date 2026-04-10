"""End-to-end integration tests with the FULL real dataset.

Verifies matching outcomes across 788 ledger rows and 934 Dropbox files.
Uses session-scoped fixtures from conftest.py for performance.
"""

import pytest


@pytest.fixture(scope="module")
def results(full_match_results):
    """Alias for the full match results fixture."""
    return full_match_results[0]


@pytest.fixture(scope="module")
def orphans(full_match_results):
    """Alias for the orphan files fixture."""
    return full_match_results[1]


class TestRealDataStats:
    """Verify overall statistics for the real matching run."""

    def test_total_counts(self, results, orphans):
        assert len(results) == 788
        assert len(orphans) == 1422

    def test_classification_distribution(self, results):
        confident = sum(1 for r in results if r.status == "Confident")
        probable = sum(1 for r in results if r.status == "Probable")
        possible = sum(1 for r in results if r.status == "Possible")
        review = sum(1 for r in results if r.status == "Review")
        no_match = sum(1 for r in results if r.status == "No Match")

        # Includes: no file vendor when ledger names vendor, and veto similarity
        # via token_set_ratio (avoids partial_ratio false positives like 'ring').
        assert confident == 297
        assert probable == 194
        assert possible == 96
        assert review == 7
        assert no_match == 194


class TestConfidentMatchesReal:
    """Spot-check real 'Confident' matches (3 signals, no ambiguity)."""

    def test_row1_deluxe(self, results):
        """Row 1: Deluxe, CA 65100, $394.55."""
        r = results[0]
        assert r.status == "Confident"
        assert r.ledger_row.vendor == "Deluxe"
        assert "amount_exact" in r.reasons
        assert "ca_match" in r.reasons
        assert "vendor_match" in r.reasons
        assert "Deluxe" in r.matched_file.original_name

    def test_row2_pot_o_gold(self, results):
        """Row 2: POT-O-GOLD, CA 50500, $208.89."""
        r = results[1]
        assert r.status == "Confident"
        assert "POT-O-GOLD" in r.matched_file.original_name

    def test_row6_vyo_structural(self, results):
        """Row 6: VYO STRUCTURAL, CA 50405, $17930."""
        r = results[5]
        assert r.status == "Confident"
        assert "VYO" in r.matched_file.original_name

    def test_row9_total_surveyors(self, results):
        """Row 9: TOTAL SURVEYORS, CA 54500, $447.50 (often near-amount in filename)."""
        r = results[8]
        assert r.status in ("Confident", "Probable")
        assert r.signal_count == 3
        if "amount_near" in r.reasons:
            assert r.status == "Probable"
        else:
            assert r.status == "Confident"

    def test_row21_linc_plumb(self, results):
        """Row 21: LINC PLUMBING, CA 53608, $11566."""
        r = results[20]
        assert r.status == "Confident"
        assert r.matched_file is not None
        assert "Linc Plumbing" in r.matched_file.original_name


class TestProbableMatchesReal:
    """Spot-check real 'Probable' matches (2 signals, or 3 signals + ambiguous)."""

    def test_row8_thomas_printwork(self, results):
        """Row 8: thomas printwork, CA 50100, $523.64."""
        r = results[7]
        assert r.status == "Probable"
        # Often missing CA in filename but has exact amount and vendor
        assert "amount_exact" in r.reasons

    def test_row14_mesken_ambiguous(self, results):
        """Row 14: MESKEN, CA 66800, $3000 (ambiguous due to multiple Mesken $3000 files)."""
        r = results[13]
        assert r.status == "Probable"
        assert r.is_ambiguous
        assert "Mesken" in r.matched_file.original_name


class TestMultiAmountMatchesReal:
    """Spot-check rows matching multi-amount files."""

    def test_row3_4_hbis_multi_amount(self, results):
        """Row 3 ($4000) and Row 4 ($2850) match the same file with $4000+$2850+$3."""
        r3 = results[2]
        r4 = results[3]
        assert r3.status == "Confident"
        assert r4.status == "Confident"
        assert r3.matched_file.original_name == r4.matched_file.original_name
        assert "$4000+$2850+$3" in r3.matched_file.original_name


class TestNoMatchReal:
    """Spot-check real rows with No Match."""

    def test_row23_mesken_no_file(self, results):
        """Row 23: MESKEN $18488.99 - No file matches."""
        r = results[22]
        assert r.status == "No Match"


class TestInvariantsReal:
    """Verify matching engine invariants on a large dataset."""

    def test_all_matched_files_unique(self, results):
        """
        Each file instance's total assignments should not exceed its capacity
        (multi-amount files can match multiple rows).
        """
        assignments_per_file = {}
        for r in results:
            if r.matched_file:
                fid = id(r.matched_file)
                assignments_per_file[fid] = assignments_per_file.get(fid, 0) + 1

        for fid, count in assignments_per_file.items():
            # Find the file object for this ID
            sample_file = next(r.matched_file for r in results if r.matched_file and id(r.matched_file) == fid)
            capacity = max(len(sample_file.amounts), 1)
            # Sum match counts as 2 assignments in current engine logic
            assert count <= capacity or "amount_sum_match" in next(r.reasons for r in results if r.matched_file and id(r.matched_file) == fid), \
                f"File {sample_file.original_name} over-assigned: {count} > {capacity}"

    def test_orphan_not_in_results(self, results, orphans):
        """Orphan file instances should not appear as a matched file for any row."""
        matched_file_ids = {id(r.matched_file) for r in results if r.matched_file}
        orphan_file_ids = {id(o) for o in orphans}
        overlap = matched_file_ids & orphan_file_ids
        assert not overlap, f"Object ID overlap between matched and orphans: {overlap}"

    def test_explanation_generates_for_all(self, results):
        from src.engine.explainer import explain
        # Only test a sample to save time
        for r in results[::100]:
            text = explain(r)
            assert len(text) > 0
            assert isinstance(text, str)
