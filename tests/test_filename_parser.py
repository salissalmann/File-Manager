"""Tests for the filename parser — covers all test filenames and edge cases."""

from datetime import date
from decimal import Decimal

import pytest

from src.parsers.filename_parser import parse_filename


class TestDateExtraction:
    """Test date parsing from various filename formats."""

    def test_dot_separated_date(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert date(2023, 3, 15) in r.dates

    def test_dash_separated_date(self):
        r = parse_filename("12-21-2022 Houston Permitting - 80.63")
        assert date(2022, 12, 21) in r.dates

    def test_compact_date(self):
        r = parse_filename("20211206_161057")
        assert date(2021, 12, 6) in r.dates

    def test_no_date(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice")
        assert r.dates == []

    def test_date_single_digit_month(self):
        r = parse_filename("6.10.2023 ferguson ca60110 $4520 invoice.pdf")
        assert date(2023, 6, 10) in r.dates

    def test_date_double_digit_month(self):
        r = parse_filename("12.27.2023 home depot $222.77 jb1523 milford.pdf")
        assert date(2023, 12, 27) in r.dates


class TestCACodeExtraction:
    """Test CA code extraction."""

    def test_ca_lowercase_no_space(self):
        r = parse_filename("6.10.2023 ferguson ca60110 $4520 invoice.pdf")
        assert "60110" in r.ca_codes

    def test_ca_mixed_case_with_space(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford")
        assert "53615" in r.ca_codes

    def test_ca_uppercase(self):
        r = parse_filename("1.05.2024 abc supply ca51010 $10000 project.pdf")
        assert "51010" in r.ca_codes

    def test_no_ca_code(self):
        r = parse_filename("12.27.2023 home depot $222.77 jb1523 milford.pdf")
        assert r.ca_codes == []

    def test_jb_not_extracted_as_ca(self):
        """Job numbers (jb1523) must NOT be extracted as CA codes."""
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert "1523" not in r.ca_codes
        assert "50408" in r.ca_codes

    def test_ca_code_1523(self):
        """CA code 1523 (Lowes) must be extracted correctly, separate from jb1523."""
        r = parse_filename("11.01.2023 lowes ca1523 $890.12 materials.pdf")
        assert "1523" in r.ca_codes

    def test_multiple_ca_codes_not_from_jb(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca99999 $17000 wrongca.pdf")
        assert "99999" in r.ca_codes


class TestAmountExtraction:
    """Test dollar amount extraction."""

    def test_whole_dollar(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert Decimal("17000") in r.amounts

    def test_decimal_amount(self):
        r = parse_filename("12.27.2023 home depot $222.77 jb1523 milford.pdf")
        assert Decimal("222.77") in r.amounts

    def test_multi_amount_with_and(self):
        r = parse_filename("3.25.2023 westheimer plumbing ca50408 $17000 and $8500 jb1523.pdf")
        assert Decimal("17000") in r.amounts
        assert Decimal("8500") in r.amounts
        assert len(r.amounts) == 2

    def test_multi_amount_ferguson(self):
        r = parse_filename("6.12.2023 ferguson ca60110 $4520 and $2260 invoice.pdf")
        assert Decimal("4520") in r.amounts
        assert Decimal("2260") in r.amounts

    def test_bare_decimal_amount(self):
        """Bare number without $ sign (Houston Permitting 80.63)."""
        r = parse_filename("12-21-2022 Houston Permitting - 80.63")
        assert Decimal("80.63") in r.amounts

    def test_no_amount(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice")
        assert r.amounts == []

    def test_invoice_number_not_amount(self):
        """'Inv 1199' is an invoice number, NOT $1,199."""
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford")
        assert Decimal("1199") not in r.amounts

    def test_invoice_number_complex_not_amount(self):
        """'Inv 113022-01' should not be extracted as an amount."""
        r = parse_filename("Inv 113022-01 Ck 1075 Marin Construction Ca 51070 Jb 1523 MIlford")
        assert Decimal("113022") not in r.amounts

    def test_amount_with_cents(self):
        r = parse_filename("9.01.2023 city electric ca70220 $1345.50 invoice.pdf")
        assert Decimal("1345.50") in r.amounts

    def test_whole_dollar_no_cents(self):
        r = parse_filename("9.02.2023 city electric ca70220 $1345 invoice.pdf")
        assert Decimal("1345") in r.amounts

    def test_amount_300(self):
        r = parse_filename("12.29.2023 home depot $300 jb1523 milford.pdf")
        assert Decimal("300") in r.amounts

    def test_amount_999_99(self):
        r = parse_filename("5.01.2023 random vendor ca99999 $999.99 misc.pdf")
        assert Decimal("999.99") in r.amounts

    def test_amount_9999_not_confused_with_99_99(self):
        """$9999 and $99.99 are very different amounts — parser must preserve decimals."""
        r1 = parse_filename("6.10.2023 ferguson ca60110 $9999 wrongamount.pdf")
        r2 = parse_filename("5.01.2023 random vendor ca99999 $999.99 misc.pdf")
        assert Decimal("9999") in r1.amounts
        assert Decimal("999.99") in r2.amounts
        assert Decimal("9999") != Decimal("999.99")


class TestInvoiceExtraction:
    """Test invoice number extraction."""

    def test_simple_invoice(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford")
        assert "1199" in r.invoice_numbers

    def test_complex_invoice(self):
        r = parse_filename("Inv 113022-01 Ck 1075 Marin Construction Ca 51070 Jb 1523 MIlford")
        assert "113022-01" in r.invoice_numbers

    def test_no_invoice(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert r.invoice_numbers == []


class TestJobNumberExtraction:
    """Test job number extraction."""

    def test_jb_lowercase(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert "1523" in r.job_numbers

    def test_jb_mixed_case(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford")
        assert "1523" in r.job_numbers

    def test_no_job_number(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice")
        assert r.job_numbers == []


class TestVendorExtraction:
    """Test vendor name token extraction."""

    def test_westheimer_plumbing(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert "westheimer" in r.vendor_tokens
        assert "plumbing" in r.vendor_tokens

    def test_home_depot(self):
        r = parse_filename("12.27.2023 home depot $222.77 jb1523 milford.pdf")
        assert "home" in r.vendor_tokens
        assert "depot" in r.vendor_tokens

    def test_ferguson(self):
        r = parse_filename("6.10.2023 ferguson ca60110 $4520 invoice.pdf")
        assert "ferguson" in r.vendor_tokens

    def test_abc_supply(self):
        r = parse_filename("1.05.2024 abc supply ca51010 $10000 project.pdf")
        assert "abc" in r.vendor_tokens
        assert "supply" in r.vendor_tokens

    def test_restan_drywall(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford")
        assert "restan" in r.vendor_tokens
        assert "drywall" in r.vendor_tokens

    def test_marin_construction(self):
        r = parse_filename("Inv 113022-01 Ck 1075 Marin Construction Ca 51070 Jb 1523 MIlford")
        assert "marin" in r.vendor_tokens
        assert "construction" in r.vendor_tokens

    def test_pot_o_gold(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice")
        assert "pot-o-gold" in r.vendor_tokens

    def test_houston_permitting(self):
        r = parse_filename("12-21-2022 Houston Permitting - 80.63")
        assert "houston" in r.vendor_tokens
        assert "permitting" in r.vendor_tokens

    def test_vyo_structural(self):
        r = parse_filename("4.01.2023 vyo structural ca80100 $12000 framing.pdf")
        assert "vyo" in r.vendor_tokens
        assert "structural" in r.vendor_tokens

    def test_noise_words_stripped(self):
        """Common words like 'invoice', 'partial' should not be in vendor tokens."""
        r = parse_filename("pot-o-gold invoice - reprint by invoice")
        assert "invoice" not in [t.lower() for t in r.vendor_tokens]
        assert "reprint" not in [t.lower() for t in r.vendor_tokens]

    def test_unparseable_filename(self):
        """Completely unparseable filename should have no vendor tokens."""
        r = parse_filename("20211206_161057")
        assert r.vendor_tokens == []


class TestFullFilenames:
    """End-to-end tests for every filename in the test set."""

    def test_f1(self):
        r = parse_filename("3.15.2023 westheimer plumbing ca50408 $17000 jb1523.pdf")
        assert date(2023, 3, 15) in r.dates
        assert "westheimer" in r.vendor_tokens
        assert "50408" in r.ca_codes
        assert Decimal("17000") in r.amounts
        assert "1523" in r.job_numbers

    def test_f3_multi_amount(self):
        r = parse_filename("3.25.2023 westheimer plumbing ca50408 $17000 and $8500 jb1523.pdf")
        assert len(r.amounts) == 2
        assert Decimal("17000") in r.amounts
        assert Decimal("8500") in r.amounts

    def test_f9_invoice_format(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford")
        assert "1199" in r.invoice_numbers
        assert "53615" in r.ca_codes
        assert "1523" in r.job_numbers
        assert "restan" in r.vendor_tokens
        assert "drywall" in r.vendor_tokens
        # 1199 should NOT be an amount
        assert Decimal("1199") not in r.amounts

    def test_f23_unparseable(self):
        r = parse_filename("20211206_161057")
        assert date(2021, 12, 6) in r.dates
        assert r.amounts == []
        assert r.ca_codes == []
        assert r.vendor_tokens == []

    def test_f24_bare_decimal(self):
        r = parse_filename("12-21-2022 Houston Permitting - 80.63")
        assert date(2022, 12, 21) in r.dates
        assert Decimal("80.63") in r.amounts
        assert "houston" in r.vendor_tokens
        assert "permitting" in r.vendor_tokens

    def test_f20_pot_o_gold(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice")
        assert r.dates == []
        assert r.amounts == []
        assert r.ca_codes == []
        assert "pot-o-gold" in r.vendor_tokens
