"""Tests for the ledger parser against the real Milford ledger."""

from datetime import date
from decimal import Decimal

import pytest

from src.parsers.ledger_parser import parse_ledger

LEDGER_PATH = "inputs/Milford-Ledger Clean.xlsx"


class TestLedgerParser:
    """Test parsing the Milford-Ledger Clean.xlsx file."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rows = parse_ledger(LEDGER_PATH)

    def test_row_count(self):
        """Should parse all 788 data rows."""
        assert len(self.rows) == 788

    def test_row1_deluxe(self):
        r = self.rows[0]
        assert r.vendor == "Deluxe"
        assert r.date == date(2021, 11, 19)
        assert r.ca_code == "65100"
        assert r.amount == Decimal("394.55")

    def test_row2_pot_o_gold(self):
        r = self.rows[1]
        assert r.vendor == "POT-O-GOLD"
        assert r.date == date(2021, 12, 8)
        assert r.ca_code == "50500"
        assert r.amount == Decimal("208.89")

    def test_row3_hbis(self):
        r = self.rows[2]
        assert r.vendor == "HBIS"
        assert r.ca_code == "50670"
        assert r.amount == Decimal("4000")

    def test_row6_vyo_structural(self):
        r = self.rows[5]
        assert r.vendor == "VYO STRUCTURAL"
        assert r.date == date(2021, 12, 10)
        assert r.ca_code == "50405"
        assert r.amount == Decimal("17930")

    def test_row7_fl_demolition(self):
        r = self.rows[6]
        assert r.vendor == "F & L DEMOLITION"
        assert r.ca_code == "51190"
        assert r.amount == Decimal("950")

    def test_row8_thomas_printwork(self):
        r = self.rows[7]
        assert r.vendor == "thomas printwork"
        assert r.ca_code == "50100"
        assert r.amount == Decimal("523.64")

    def test_row9_total_surveyors(self):
        r = self.rows[8]
        assert r.vendor == "TOTAL SURVEYORS"
        assert r.ca_code == "54500"
        assert r.amount == Decimal("447.5")

    def test_row12_home_depot(self):
        r = self.rows[11]
        assert r.vendor == "HOME DEPOT"
        assert r.ca_code == "50408"
        assert r.amount == Decimal("222.77")

    def test_row14_mesken(self):
        r = self.rows[13]
        assert r.vendor == "MESKEN"
        assert r.ca_code == "66800"
        assert r.amount == Decimal("3000")

    def test_row21_linc_plumbing(self):
        r = self.rows[20]
        assert r.vendor == "LINC PLUMBING"
        assert r.ca_code == "53608"
        assert r.amount == Decimal("11566")

    def test_vendor_case_preserved(self):
        """Mixed-case vendor names are preserved exactly."""
        r = self.rows[7]  # thomas printwork — lowercase in source
        assert r.vendor == "thomas printwork"

    def test_ca_extraction_from_account(self):
        """CA codes are extracted from 'NNNNN · Description' format."""
        r = self.rows[1]  # POT-O-GOLD: "50500 · Equipment Rental for Jobs"
        assert r.ca_code == "50500"

    def test_all_rows_have_required_fields(self):
        """Every row must have vendor, date, ca_code, and amount."""
        for r in self.rows:
            assert r.vendor, f"Row {r.index} missing vendor"
            assert r.date is not None, f"Row {r.index} missing date"
            assert r.ca_code, f"Row {r.index} missing CA code"
            assert r.amount is not None, f"Row {r.index} missing amount"

    def test_ca_codes_are_clean_strings(self):
        """CA codes should be clean strings (no .0 from float conversion)."""
        for r in self.rows:
            assert "." not in r.ca_code, f"Row {r.index} CA has decimal: {r.ca_code}"

    def test_amounts_are_decimal(self):
        """All amounts should be Decimal values."""
        for r in self.rows:
            assert isinstance(r.amount, Decimal), f"Row {r.index} amount is not Decimal"

    def test_dates_in_reasonable_range(self):
        """All dates should be between 2021 and 2025."""
        for r in self.rows:
            assert date(2021, 1, 1) <= r.date <= date(2025, 12, 31), (
                f"Row {r.index} date {r.date} out of range"
            )
