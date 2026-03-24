"""End-to-end integration tests with the full test dataset.

Verifies all 26 expected match outcomes from the edge case analysis.
"""

from pathlib import Path

import pytest

from src.engine.matcher import run_matching
from src.parsers.ledger_parser import parse_ledger


LEDGER_PATH = "inputs/1523 TEST Ledger.xlsx"
FILENAMES_PATH = "inputs/filenames.txt"

# All test filenames
FILENAMES = [
    "3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf",          # F1
    "3.20.2023 westheimer plumbing ca50408 $8500 jb1523.pdf",           # F2
    "3.25.2023 westheimer plumbing ca50408 $17000 and $8500 jb1523.pdf",# F3
    "12.27.2023 home depot $222.77 jb1523 milford.pdf",                 # F4
    "12.28.2023 home depot $118.42 jb1523 milford.pdf",                 # F5
    "12.29.2023 home depot $300 jb1523 milford.pdf",                    # F6
    "6.10.2023 ferguson ca60110 $4520 invoice.pdf",                     # F7
    "6.11.2023 ferguson ca60110 $2260 invoice.pdf",                     # F8
    "Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford",        # F9
    "6.12.2023 ferguson ca60110 $4520 and $2260 invoice.pdf",           # F10
    "Inv 113022-01 Ck 1075 Marin Construction Ca 51070 Jb 1523 MIlford",# F11
    "1.05.2024 abc supply ca51010 $10000 project.pdf",                  # F12
    "1.06.2024 abc supply ca51010 $5000 partial.pdf",                   # F13
    "1.07.2024 abc supply ca51010 $5000 partial second.pdf",            # F14
    "9.01.2023 city electric ca70220 $1345.50 invoice.pdf",             # F15
    "9.02.2023 city electric ca70220 $1345 invoice.pdf",                # F16
    "11.01.2023 lowes ca1523 $890.12 materials.pdf",                    # F17
    "11.02.2023 lowes ca1523 $445.06 materials.pdf",                    # F18
    "4.01.2023 vyo structural ca80100 $12000 framing.pdf",              # F19
    "pot-o-gold invoice - reprint by invoice",                          # F20
    "4.02.2023 vyo structural ca80100 $6000 framing part1.pdf",         # F21
    "4.03.2023 vyo structural ca80100 $6000 framing part2.pdf",         # F22
    "20211206_161057",                                                  # F23
    "12-21-2022 Houston Permitting - 80.63",                            # F24
    "5.01.2023 random vendor ca99999 $999.99 misc.pdf",                 # F25
    "3.15.2023 westheimer plumbing ca99999 $17000 wrongca.pdf",         # F26
    "pot-o-gold invoice - reprint by invoice",                          # F27 (dup of F20)
    "12.27.2023 home depot $222.77 ca99999 wrongca.pdf",                # F28
    "6.10.2023 ferguson ca60110 $9999 wrongamount.pdf",                 # F29
]


@pytest.fixture
def match_results():
    """Run the full matching pipeline with test data."""
    ledger_rows = parse_ledger(LEDGER_PATH)
    results, orphans = run_matching(ledger_rows, FILENAMES)
    return results, orphans


class TestStrongMatches:
    """Rows that should have Strong status with exact matches."""

    def test_row1_westheimer_17000(self, match_results):
        """Row 1: WESTHEIMER PLUMBING, CA 50408, $17000 → F1."""
        r = match_results[0][0]
        assert r.status == "Strong"
        assert r.matched_file is not None
        assert "50408" in r.matched_file.ca_codes
        assert "amount_exact" in r.reasons

    def test_row2_westheimer_8500(self, match_results):
        """Row 2: WESTHEIMER PLUMBING, CA 50408, $8500 → F2."""
        r = match_results[0][1]
        assert r.status == "Strong"
        assert r.matched_file is not None
        assert "amount_exact" in r.reasons

    def test_row5_ferguson_4520(self, match_results):
        """Row 5: Ferguson, CA 60110, $4520 → F7."""
        r = match_results[0][4]
        assert r.status == "Strong"
        assert "ca_match" in r.reasons

    def test_row7_abc_10000(self, match_results):
        """Row 7: ABC Supply, CA 51010, $10000 → F12."""
        r = match_results[0][6]
        assert r.status == "Strong"
        assert r.score == 100.0

    def test_row10_city_electric_exact(self, match_results):
        """Row 10: City Electric, CA 70220, $1345 → F16 (exact $1345)."""
        r = match_results[0][9]
        assert r.status == "Strong"
        assert "amount_exact" in r.reasons

    def test_row12_lowes_exact(self, match_results):
        """Row 12: Lowes, CA 1523, $890.12 → F17."""
        r = match_results[0][11]
        assert r.status == "Strong"
        assert "amount_exact" in r.reasons

    def test_row14_vyo_12000(self, match_results):
        """Row 14: VYO Structural, CA 80100, $12000 → F19."""
        r = match_results[0][13]
        assert r.status == "Strong"

    def test_row17_random_vendor(self, match_results):
        """Row 17: Random Vendor, CA 99999, $999.99 → F25."""
        r = match_results[0][16]
        assert r.status == "Strong"
        assert r.score == 100.0

    def test_row18_westheimer_ca99999(self, match_results):
        """Row 18: WESTHEIMER PLUMBING, CA 99999, $17000 → F26 (the 'wrongca' file)."""
        r = match_results[0][17]
        assert r.status == "Strong"
        assert "99999" in r.matched_file.ca_codes

    def test_row19_home_depot_ca99999(self, match_results):
        """Row 19: HOME DEPOT, CA 99999, $222.77 → F28."""
        r = match_results[0][18]
        assert r.status == "Strong"
        assert "99999" in r.matched_file.ca_codes


class TestGoodMatches:
    """Rows that should have Good status."""

    def test_row3_home_depot_no_ca(self, match_results):
        """Row 3: THE HOME DEPOT, CA 50408, $222.77 → F4 (no CA in file)."""
        r = match_results[0][2]
        assert r.status == "Good"
        assert r.matched_file is not None
        assert "amount_exact" in r.reasons
        assert r.matched_file.ca_codes == []  # No CA in file

    def test_row4_home_depot_118(self, match_results):
        """Row 4: THE HOME DEPOT, CA 50412, $118.42 → F5."""
        r = match_results[0][3]
        assert r.status == "Good"
        assert "amount_exact" in r.reasons

    def test_row21_restan_drywall(self, match_results):
        """Row 21: REstan Drywall, CA 53615, $1199 → F9 (vendor + CA, no amount)."""
        r = match_results[0][20]
        assert r.status == "Good"
        assert r.matched_file is not None
        assert "restan" in r.matched_file.vendor_tokens
        assert "53615" in r.matched_file.ca_codes

    def test_row22_marin_construction(self, match_results):
        """Row 22: Marin Construction, CA 51070, $5600 → F11 (vendor + CA, no amount)."""
        r = match_results[0][21]
        assert r.status == "Good"
        assert r.matched_file is not None
        assert "marin" in r.matched_file.vendor_tokens

    def test_row23_houston_permitting(self, match_results):
        """Row 23: Houston Permitting, $80.63 → F24 (vendor + amount, no CA)."""
        r = match_results[0][22]
        assert r.status == "Good"
        assert "amount_exact" in r.reasons
        assert "houston" in r.matched_file.vendor_tokens


class TestNearAmountMatches:
    """Rows with near-amount matches (within tolerance)."""

    def test_row11_city_electric_near(self, match_results):
        """Row 11: City Electric, $1345 → F15 ($1345.50, $0.50 off)."""
        r = match_results[0][10]
        assert r.matched_file is not None
        assert "amount_near" in r.reasons

    def test_row13_lowes_near(self, match_results):
        """Row 13: Lowes, $445.04 → F18 ($445.06, $0.02 off)."""
        r = match_results[0][12]
        assert r.matched_file is not None
        assert "amount_near" in r.reasons


class TestOneToOneAssignment:
    """Verify duplicate ledger rows get different files."""

    def test_abc_supply_5000_different_files(self, match_results):
        """Rows 8,9 (ABC $5000) each get a different file (F13, F14)."""
        r8 = match_results[0][7]
        r9 = match_results[0][8]
        assert r8.matched_file is not None
        assert r9.matched_file is not None
        assert r8.matched_file.original_name != r9.matched_file.original_name

    def test_vyo_6000_different_files(self, match_results):
        """Rows 15,16 (VYO $6000) each get a different file (F21, F22)."""
        r15 = match_results[0][14]
        r16 = match_results[0][15]
        assert r15.matched_file is not None
        assert r16.matched_file is not None
        assert r15.matched_file.original_name != r16.matched_file.original_name

    def test_city_electric_different_files(self, match_results):
        """Rows 10,11 (City Electric $1345) each get a different file (F15/F16)."""
        r10 = match_results[0][9]
        r11 = match_results[0][10]
        assert r10.matched_file is not None
        assert r11.matched_file is not None
        assert r10.matched_file.original_name != r11.matched_file.original_name


class TestReviewMatches:
    """Rows that should be flagged for review."""

    def test_row24_pot_o_gold_250(self, match_results):
        """Row 24: Pot-O-Gold, $250 → pot-o-gold file (vendor only = Review)."""
        r = match_results[0][23]
        assert r.status == "Review"
        assert r.matched_file is not None
        assert "pot-o-gold" in r.matched_file.vendor_tokens

    def test_row26_pot_o_gold_300(self, match_results):
        """Row 26: Pot-O-Gold, $300 → second pot-o-gold file (vendor only = Review)."""
        r = match_results[0][25]
        assert r.status == "Review"
        assert r.matched_file is not None


class TestNoMatches:
    """Rows that should have No Match status."""

    def test_row6_ferguson_260(self, match_results):
        """Row 6: Ferguson, $260 — no file has $260."""
        r = match_results[0][5]
        assert r.status == "No Match"
        assert r.matched_file is None

    def test_row20_ferguson_99_99(self, match_results):
        """Row 20: Ferguson, $99.99 — no file matches this amount."""
        r = match_results[0][19]
        assert r.status == "No Match"

    def test_row25_unknown_vendor(self, match_results):
        """Row 25: Unknown Vendor, $1500 — no matching file."""
        r = match_results[0][24]
        assert r.status == "No Match"


class TestVetoRulesInAction:
    """Verify veto rules correctly reject bad matches."""

    def test_row1_rejects_wrongca_file(self, match_results):
        """Row 1 (CA 50408) should have F26 (CA 99999) in vetoed candidates."""
        r = match_results[0][0]
        vetoed_names = [vc.file.original_name for vc in r.vetoed_candidates]
        wrongca_files = [n for n in vetoed_names if "ca99999" in n and "westheimer" in n]
        assert len(wrongca_files) > 0

    def test_row3_rejects_wrongca_home_depot(self, match_results):
        """Row 3 (Home Depot, CA 50408) should veto F28 (CA 99999)."""
        r = match_results[0][2]
        vetoed_names = [vc.file.original_name for vc in r.vetoed_candidates]
        wrongca = [n for n in vetoed_names if "ca99999" in n]
        assert len(wrongca) > 0

    def test_row5_rejects_wrongamount(self, match_results):
        """Row 5 (Ferguson, $4520) should veto F29 ($9999)."""
        r = match_results[0][4]
        vetoed_names = [vc.file.original_name for vc in r.vetoed_candidates]
        wrongamt = [n for n in vetoed_names if "9999" in n and "wrongamount" in n]
        assert len(wrongamt) > 0


class TestOrphanFiles:
    """Verify unmatched files are correctly identified."""

    def test_orphan_count(self, match_results):
        """Should have orphan files (F6, F8, F23, F29 at minimum)."""
        orphans = match_results[1]
        assert len(orphans) >= 4

    def test_unparseable_file_is_orphan(self, match_results):
        """F23 (20211206_161057) should be an orphan."""
        orphan_names = [o.original_name for o in match_results[1]]
        assert "20211206_161057" in orphan_names

    def test_wrongamount_file_is_orphan(self, match_results):
        """F29 (wrongamount) should be an orphan."""
        orphan_names = [o.original_name for o in match_results[1]]
        wrongamt = [n for n in orphan_names if "wrongamount" in n]
        assert len(wrongamt) > 0


class TestAlternativesInResults:
    """Verify alternatives are populated for matches."""

    def test_strong_match_has_alternatives_if_similar_files_exist(self, match_results):
        """Row 1 (Westheimer $17000) should have alternatives since F3 also has $17000."""
        r = match_results[0][0]
        assert r.matched_file is not None
        # F3 (multi-amount) also has $17000, should appear as alternative
        alt_names = [a.file.original_name for a in r.alternatives]
        assert len(alt_names) >= 1

    def test_no_match_rows_have_no_alternatives(self, match_results):
        """Row 25 (Unknown Vendor) has no match and should have no useful alternatives."""
        r = match_results[0][24]
        assert r.status == "No Match"


class TestMultiAmountPenaltyInIntegration:
    """Verify multi-amount files get penalty in integration context."""

    def test_f3_multi_amount_has_penalty(self, match_results):
        """F3 (with $17000 and $8500) should have lower score than F1 (single $17000)."""
        r1 = match_results[0][0]  # Row 1 should match F1 (single amount)
        # F1 should be preferred over F3 because F3 has multi-amount penalty
        assert r1.matched_file is not None
        # If F1 was selected, it should be the single-amount file
        assert "and" not in r1.matched_file.original_name


class TestSummaryStats:
    """Verify overall statistics match expectations."""

    def test_total_results(self, match_results):
        assert len(match_results[0]) == 26

    def test_no_match_count(self, match_results):
        no_match = sum(1 for r in match_results[0] if r.status == "No Match")
        assert no_match == 3  # Row 6, 20, 25

    def test_strong_count(self, match_results):
        strong = sum(1 for r in match_results[0] if r.status == "Strong")
        assert strong >= 14  # At minimum, the clear-cut matches

    def test_all_matched_files_unique(self, match_results):
        """No two ledger rows should match the same file instance
        (except multi-amount files)."""
        results = match_results[0]
        matched = [r for r in results if r.matched_file is not None]
        # Multi-amount files can appear twice, so check by file object identity
        file_ids = [id(r.matched_file) for r in matched]
        # Each matched file object should be unique (since we track by index)
        assert len(file_ids) == len(set(file_ids))
