"""Tests for the ledger parser."""

from datetime import date
from decimal import Decimal

import pytest

from src.parsers.ledger_parser import parse_ledger


LEDGER_PATH = "inputs/1523 TEST Ledger.xlsx"


class TestLedgerParser:
    """Test parsing the test ledger file."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rows = parse_ledger(LEDGER_PATH)

    def test_row_count(self):
        """Should parse all 26 data rows."""
        assert len(self.rows) == 26

    def test_first_row(self):
        r = self.rows[0]
        assert r.vendor == "WESTHEIMER PLUMBING"
        assert r.date == date(2023, 5, 11)
        assert r.ca_code == "50408"
        assert r.amount == Decimal("17000")

    def test_home_depot_row(self):
        r = self.rows[2]  # 3rd data row
        assert r.vendor == "THE HOME DEPOT"
        assert r.ca_code == "50408"
        assert r.amount == Decimal("222.77")

    def test_ferguson_260(self):
        """Ferguson row with amount 260 (potential edge case)."""
        r = self.rows[5]
        assert "Ferguson" in r.vendor or "ferguson" in r.vendor.lower()
        assert r.ca_code == "60110"
        assert r.amount == Decimal("260")

    def test_lowes_amount_precision(self):
        """Lowes $445.04 — verify decimal precision."""
        r = self.rows[12]
        assert "Lowes" in r.vendor or "lowes" in r.vendor.lower()
        assert r.amount == Decimal("445.04")

    def test_restan_drywall(self):
        r = self.rows[20]
        assert "REstan" in r.vendor or "restan" in r.vendor.lower()
        assert r.ca_code == "53615"
        assert r.amount == Decimal("1199")

    def test_houston_permitting(self):
        r = self.rows[22]
        assert "Houston" in r.vendor
        assert r.ca_code == "55000"
        assert r.amount == Decimal("80.63")

    def test_pot_o_gold(self):
        r = self.rows[23]
        assert "Pot" in r.vendor or "pot" in r.vendor.lower()
        assert r.ca_code == "50500"
        assert r.amount == Decimal("250")

    def test_unknown_vendor(self):
        r = self.rows[24]
        assert "Unknown" in r.vendor
        assert r.ca_code == "56000"
        assert r.amount == Decimal("1500")

    def test_last_row(self):
        r = self.rows[25]
        assert "Pot" in r.vendor or "pot" in r.vendor.lower()
        assert r.amount == Decimal("300")

    def test_all_rows_have_required_fields(self):
        """Every row must have vendor, date, ca_code, and amount."""
        for r in self.rows:
            assert r.vendor, f"Row {r.index} missing vendor"
            assert r.date is not None, f"Row {r.index} missing date"
            assert r.ca_code, f"Row {r.index} missing CA code"
            assert r.amount is not None, f"Row {r.index} missing amount"

    def test_ca_codes_are_strings(self):
        """CA codes should be clean strings (no .0 from float conversion)."""
        for r in self.rows:
            assert "." not in r.ca_code, f"Row {r.index} CA has decimal: {r.ca_code}"
