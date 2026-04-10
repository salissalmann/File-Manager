"""Tests for the filename parser — uses real Dropbox filenames."""

from datetime import date
from decimal import Decimal

import pytest

from src.parsers.filename_parser import parse_filename


class TestDateExtraction:
    """Test date parsing from various real filename formats."""

    def test_dot_separated_date_vyo(self):
        r = parse_filename("12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf")
        assert date(2021, 12, 10) in r.dates

    def test_dash_separated_date_houston(self):
        r = parse_filename("12-21-2022 Houston Permitting - 80.63.pdf")
        assert date(2022, 12, 21) in r.dates

    def test_date_single_digit_month(self):
        r = parse_filename("1.21.2022 mesken Ca 66800 jb 1523 Milford.pdf")
        assert date(2022, 1, 21) in r.dates

    def test_date_double_digit_month_home_depot(self):
        r = parse_filename("12.27.2021  the home depost $222.77 jb 1523 milford.pdf")
        assert date(2021, 12, 27) in r.dates

    def test_no_date_pot_o_gold(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice.pdf")
        assert r.dates == []

    def test_dot_date_thomas_printwork(self):
        r = parse_filename("12.17.2021 thomas printwork $523.64 jb 1523 milford.pdf")
        assert date(2021, 12, 17) in r.dates

    def test_dash_date_hbis(self):
        r = parse_filename("12-5-2022 hbis $2285  and 79.98 fee Jb 1523 Milford.pdf")
        assert date(2022, 12, 5) in r.dates


class TestCACodeExtraction:
    """Test CA code extraction from real filenames."""

    def test_ca_uppercase_vyo(self):
        r = parse_filename("12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf")
        assert "50405" in r.ca_codes

    def test_ca_mixed_case_restan(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford.pdf")
        assert "53615" in r.ca_codes

    def test_ca_no_space(self):
        r = parse_filename("12.30.2022 HBIS CA50670 $2364.98 Jb 1523 Milford.pdf")
        assert "50670" in r.ca_codes

    def test_no_ca_code_home_depot(self):
        r = parse_filename("12.27.2021  the home depost $222.77 jb 1523 milford.pdf")
        assert r.ca_codes == []

    def test_jb_not_extracted_as_ca(self):
        """Job numbers (jb 1523) must NOT be extracted as CA codes."""
        r = parse_filename("Linc Plumbing Ca 53608 $11566 jb 1523 MIlford Inv 8496634 Ck 1010.pdf")
        assert "1523" not in r.ca_codes
        assert "53608" in r.ca_codes

    def test_ca_from_altura(self):
        r = parse_filename("01.20.2023 Altura Stone CA 50415 $5,842.50 Jb 1523 Milford.pdf")
        assert "50415" in r.ca_codes

    def test_ca_from_complete_glass(self):
        r = parse_filename("Complete Glass & More CA 53633 $3150.00 Jb 1523 MIlford Inv 1173 Ck 1095.pdf")
        assert "53633" in r.ca_codes


class TestAmountExtraction:
    """Test dollar amount extraction from real filenames."""

    def test_whole_dollar_vyo(self):
        r = parse_filename("12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf")
        assert Decimal("17930") in r.amounts

    def test_decimal_amount_home_depot(self):
        r = parse_filename("12.27.2021  the home depost $222.77 jb 1523 milford.pdf")
        assert Decimal("222.77") in r.amounts

    def test_comma_delimited_amount_altura(self):
        """$5,842.50 with comma should be parsed correctly."""
        r = parse_filename("01.20.2023 Altura Stone CA 50415 $5,842.50 Jb 1523 Milford.pdf")
        assert Decimal("5842.50") in r.amounts

    def test_multi_amount_hbis(self):
        """File with '$2285 and 79.98' should extract the dollar amount."""
        r = parse_filename("12-5-2022 hbis $2285  and 79.98 fee Jb 1523 Milford.pdf")
        assert Decimal("2285") in r.amounts

    def test_bare_decimal_houston(self):
        """Bare number without $ sign (Houston Permitting 80.63)."""
        r = parse_filename("12-21-2022 Houston Permitting - 80.63.pdf")
        assert Decimal("80.63") in r.amounts

    def test_no_amount_pot_o_gold(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice.pdf")
        assert r.amounts == []

    def test_invoice_number_not_amount(self):
        """'Inv 1199' is an invoice number, NOT $1,199."""
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford.pdf")
        assert Decimal("1199") not in r.amounts

    def test_invoice_number_complex_not_amount(self):
        """'Inv 8496634' should not be extracted as an amount."""
        r = parse_filename("Linc Plumbing Ca 53608 $11566 jb 1523 MIlford Inv 8496634 Ck 1010.pdf")
        assert Decimal("8496634") not in r.amounts
        assert Decimal("11566") in r.amounts

    def test_amount_with_cents_pot_o_gold(self):
        r = parse_filename("12.8.2021 pot o gold $208.89 jb 1523 milford.pdf")
        assert Decimal("208.89") in r.amounts

    def test_amount_with_cents_thomas(self):
        r = parse_filename("12.17.2021 thomas printwork $523.64 jb 1523 milford.pdf")
        assert Decimal("523.64") in r.amounts

    def test_comma_amount_complete_glass(self):
        r = parse_filename("Complete Glass & More CA 53633 $3150.00 Jb 1523 MIlford Inv 1173 Ck 1095.pdf")
        assert Decimal("3150.00") in r.amounts

    def test_amount_with_plus_hbis_multi(self):
        """HBIS file with $4000+$2850+$3 format."""
        r = parse_filename("12.09.2021 HBIS Ck 1000 Ca 50670 Builders Risk Jb 1523 MIlford $4000+$2850+$3.pdf")
        assert Decimal("4000") in r.amounts


class TestInvoiceExtraction:
    """Test invoice number extraction from real filenames."""

    def test_simple_invoice_restan(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford.pdf")
        assert "1199" in r.invoice_numbers

    def test_long_invoice_linc(self):
        r = parse_filename("Linc Plumbing Ca 53608 $11566 jb 1523 MIlford Inv 8496634 Ck 1010.pdf")
        assert "8496634" in r.invoice_numbers

    def test_invoice_legacy_design(self):
        r = parse_filename("Inv 7807 Ck 1005 Legacy Design Construction Ca 53604 Jb 1523 Milford.pdf")
        assert "7807" in r.invoice_numbers

    def test_no_invoice_home_depot(self):
        r = parse_filename("12.27.2021  the home depost $222.77 jb 1523 milford.pdf")
        assert r.invoice_numbers == []


class TestJobNumberExtraction:
    """Test job number extraction from real filenames."""

    def test_jb_lowercase_spaced(self):
        r = parse_filename("12.8.2021 pot o gold $208.89 jb 1523 milford.pdf")
        assert "1523" in r.job_numbers

    def test_jb_mixed_case(self):
        r = parse_filename("Inv 1199 Ck 1081 REstan Drywall Ca 53615 Jb 1523 Milford.pdf")
        assert "1523" in r.job_numbers

    def test_no_job_number(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice.pdf")
        assert r.job_numbers == []


class TestVendorExtraction:
    """Test vendor name token extraction from real filenames."""

    def test_vyo(self):
        r = parse_filename("12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf")
        assert "vyo" in r.vendor_tokens

    def test_home_depot_misspelled(self):
        r = parse_filename("12.27.2021  the home depost $222.77 jb 1523 milford.pdf")
        assert "home" in r.vendor_tokens
        assert "depost" in r.vendor_tokens

    def test_linc_plumbing(self):
        r = parse_filename("Linc Plumbing Ca 53608 $11566 jb 1523 MIlford Inv 8496634 Ck 1010.pdf")
        assert "linc" in r.vendor_tokens
        assert "plumbing" in r.vendor_tokens

    def test_legacy_design_construction(self):
        r = parse_filename("Inv 7807 Ck 1005 Legacy Design Construction Ca 53604 Jb 1523 Milford.pdf")
        assert "legacy" in r.vendor_tokens
        assert "design" in r.vendor_tokens
        assert "construction" not in r.vendor_tokens # Now a noise word

    def test_pot_o_gold_hyphen(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice.pdf")
        assert "pot-o-gold" in r.vendor_tokens

    def test_mesken(self):
        r = parse_filename("1.21.2022 mesken Ca 66800 jb 1523 Milford.pdf")
        assert "mesken" in r.vendor_tokens

    def test_thomas_printwork(self):
        r = parse_filename("12.17.2021 thomas printwork $523.64 jb 1523 milford.pdf")
        assert "thomas" in r.vendor_tokens
        assert "printwork" in r.vendor_tokens

    def test_houston_permitting(self):
        r = parse_filename("12-21-2022 Houston Permitting - 80.63.pdf")
        assert "houston" in r.vendor_tokens
        assert "permitting" in r.vendor_tokens

    def test_noise_words_stripped(self):
        """Common words like 'invoice', 'reprint' should not be in vendor tokens."""
        r = parse_filename("pot-o-gold invoice - reprint by invoice.pdf")
        assert "invoice" not in [t.lower() for t in r.vendor_tokens]
        assert "reprint" not in [t.lower() for t in r.vendor_tokens]


class TestFullFilenames:
    """End-to-end tests for representative real filenames."""

    def test_vyo_confident_file(self):
        r = parse_filename("12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf")
        assert date(2021, 12, 10) in r.dates
        assert "vyo" in r.vendor_tokens
        assert "50405" in r.ca_codes
        assert Decimal("17930") in r.amounts

    def test_pot_o_gold_amount_file(self):
        r = parse_filename("12.8.2021 POT-O-GOLD CA 50500 $208.89.pdf")
        assert date(2021, 12, 8) in r.dates
        assert "pot-o-gold" in r.vendor_tokens
        assert "50500" in r.ca_codes
        assert Decimal("208.89") in r.amounts

    def test_home_depot_misspelled_file(self):
        r = parse_filename("12.27.2021  the home depost $222.77 jb 1523 milford.pdf")
        assert date(2021, 12, 27) in r.dates
        assert "home" in r.vendor_tokens
        assert "depost" in r.vendor_tokens
        assert Decimal("222.77") in r.amounts
        assert r.ca_codes == []

    def test_thomas_printwork_file(self):
        r = parse_filename("12.17.2021 thomas printwork $523.64 jb 1523 milford.pdf")
        assert date(2021, 12, 17) in r.dates
        assert "thomas" in r.vendor_tokens
        assert Decimal("523.64") in r.amounts
        assert "1523" in r.job_numbers

    def test_mesken_no_amount(self):
        r = parse_filename("1.21.2022 mesken Ca 66800 jb 1523 Milford.pdf")
        assert date(2022, 1, 21) in r.dates
        assert "mesken" in r.vendor_tokens
        assert "66800" in r.ca_codes
        assert r.amounts == []

    def test_linc_plumbing_full(self):
        r = parse_filename("Linc Plumbing Ca 53608 $11566 jb 1523 MIlford Inv 8496634 Ck 1010.pdf")
        assert "linc" in r.vendor_tokens
        assert "plumbing" in r.vendor_tokens
        assert "53608" in r.ca_codes
        assert Decimal("11566") in r.amounts
        assert "8496634" in r.invoice_numbers
        assert "1523" in r.job_numbers

    def test_legacy_design_invoice(self):
        r = parse_filename("Inv 7807 Ck 1005 Legacy Design Construction Ca 53604 Jb 1523 Milford.pdf")
        assert "7807" in r.invoice_numbers
        assert "legacy" in r.vendor_tokens
        assert "53604" in r.ca_codes
        assert "1523" in r.job_numbers

    def test_houston_permitting_bare_decimal(self):
        r = parse_filename("12-21-2022 Houston Permitting - 80.63.pdf")
        assert date(2022, 12, 21) in r.dates
        assert Decimal("80.63") in r.amounts
        assert "houston" in r.vendor_tokens
        assert "permitting" in r.vendor_tokens

    def test_pot_o_gold_vendor_only(self):
        r = parse_filename("pot-o-gold invoice - reprint by invoice.pdf")
        assert r.dates == []
        assert r.amounts == []
        assert r.ca_codes == []
        assert "pot-o-gold" in r.vendor_tokens

    def test_altura_comma_amount(self):
        r = parse_filename("01.20.2023 Altura Stone CA 50415 $5,842.50 Jb 1523 Milford.pdf")
        assert date(2023, 1, 20) in r.dates
        assert "altura" in r.vendor_tokens
        assert "50415" in r.ca_codes
        assert Decimal("5842.50") in r.amounts

    def test_restan_with_amount(self):
        r = parse_filename("Inv 1199 Ck 1081 RESTAN DRYWALL $12,160.64 Ca 53615 Jb 1523 Milford.pdf")
        assert "1199" in r.invoice_numbers
        assert "restan" in r.vendor_tokens
        assert "53615" in r.ca_codes
        assert Decimal("12160.64") in r.amounts
