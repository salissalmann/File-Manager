"""Parse unstructured filenames into structured FileRecord objects."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

import config
from src.models import FileRecord


# --- Regex patterns ---

# Date: M.DD.YYYY or MM.DD.YYYY (dot-separated)
_DATE_DOT = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")

# Date: MM-DD-YYYY (dash-separated)
_DATE_DASH = re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b")

# Date: YYYYMMDD (optionally followed by _HHMMSS)
_DATE_COMPACT = re.compile(r"\b(\d{4})(\d{2})(\d{2})(?:_\d{6})?\b")

# CA code: "ca" or "Ca" or "CA" followed by optional space and digits
_CA_CODE = re.compile(r"\b[Cc][Aa]\s*(\d+)\b")

# Dollar amount: $ followed by digits with optional decimals and commas
_DOLLAR_AMOUNT = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)\b")

# Invoice number: "Inv" followed by space and alphanumeric/dash pattern
_INVOICE = re.compile(r"\b[Ii]nv\s+([\w-]+)\b")

# Job number: "jb" or "Jb" or "JB" followed by optional space and digits
_JOB_NUMBER = re.compile(r"\b[Jj][Bb]\s*(\d+)\b")

# Check number: "Ck" followed by space and digits
_CHECK_NUMBER = re.compile(r"\b[Cc][Kk]\s+(\d+)\b")

# Bare decimal number (e.g., "80.63" without $) - used as fallback
_BARE_DECIMAL = re.compile(r"(?<!\d)(\d+\.\d{2})(?!\d)")


def parse_filename(filename: str) -> FileRecord:
    """Parse an unstructured filename into a structured FileRecord.

    Extracts dates, CA codes, amounts, invoice numbers, job numbers,
    and vendor name tokens from the filename.
    """
    record = FileRecord(original_name=filename)

    # Work on a mutable copy for token removal
    remaining = filename

    # Strip known file extensions only (not bare decimals like "80.63")
    remaining = re.sub(r"\.(pdf|xlsx|xls|doc|docx|csv|txt|jpg|png)$", "", remaining, flags=re.IGNORECASE)

    # --- Extract dates ---
    remaining = _extract_dates(remaining, record)

    # --- Extract invoice numbers (before amounts, so "Inv 1199" isn't treated as $) ---
    remaining = _extract_invoices(remaining, record)

    # --- Extract check numbers (remove so they don't pollute vendor) ---
    remaining = _extract_check_numbers(remaining)

    # --- Extract CA codes ---
    remaining = _extract_ca_codes(remaining, record)

    # --- Extract job numbers ---
    remaining = _extract_job_numbers(remaining, record)

    # --- Extract dollar amounts ---
    remaining = _extract_amounts(remaining, record)

    # --- Extract vendor tokens from what's left ---
    _extract_vendor_tokens(remaining, record)

    return record


def _extract_dates(text: str, record: FileRecord) -> str:
    """Extract dates from text and return text with dates removed."""
    # Dot-separated dates (most common in the test data)
    for match in _DATE_DOT.finditer(text):
        month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            record.dates.append(date(year, month, day))
        except ValueError:
            pass
    text = _DATE_DOT.sub("", text)

    # Dash-separated dates
    for match in _DATE_DASH.finditer(text):
        month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            record.dates.append(date(year, month, day))
        except ValueError:
            pass
    text = _DATE_DASH.sub("", text)

    # Compact dates (YYYYMMDD)
    for match in _DATE_COMPACT.finditer(text):
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        # Only accept if it looks like a real date (year 2000-2030)
        if 2000 <= year <= 2030:
            try:
                record.dates.append(date(year, month, day))
            except ValueError:
                pass
    text = _DATE_COMPACT.sub("", text)

    return text


def _extract_invoices(text: str, record: FileRecord) -> str:
    """Extract invoice numbers and return text with them removed."""
    for match in _INVOICE.finditer(text):
        record.invoice_numbers.append(match.group(1))
    text = _INVOICE.sub("", text)
    return text


def _extract_check_numbers(text: str) -> str:
    """Remove check numbers from text (not stored, just cleaned)."""
    return _CHECK_NUMBER.sub("", text)


def _extract_ca_codes(text: str, record: FileRecord) -> str:
    """Extract CA codes and return text with them removed."""
    for match in _CA_CODE.finditer(text):
        record.ca_codes.append(match.group(1))
    text = _CA_CODE.sub("", text)
    return text


def _extract_job_numbers(text: str, record: FileRecord) -> str:
    """Extract job numbers and return text with them removed."""
    for match in _JOB_NUMBER.finditer(text):
        record.job_numbers.append(match.group(1))
    text = _JOB_NUMBER.sub("", text)
    return text


def _extract_amounts(text: str, record: FileRecord) -> str:
    """Extract dollar amounts and return text with them removed.

    Falls back to bare decimal numbers if no $ amounts found.
    """
    found_dollar = False
    for match in _DOLLAR_AMOUNT.finditer(text):
        found_dollar = True
        raw = match.group(1).replace(",", "")
        try:
            record.amounts.append(Decimal(raw))
        except InvalidOperation:
            pass
    text = _DOLLAR_AMOUNT.sub("", text)

    # Fallback: bare decimal numbers (e.g., "80.63") only if no $ amounts found
    if not found_dollar:
        for match in _BARE_DECIMAL.finditer(text):
            raw = match.group(1)
            try:
                val = Decimal(raw)
                # Only accept reasonable amounts (> $1, < $1M)
                if Decimal("1") <= val <= Decimal("999999"):
                    record.amounts.append(val)
            except InvalidOperation:
                pass
        text = _BARE_DECIMAL.sub("", text)

    return text


def _extract_vendor_tokens(text: str, record: FileRecord) -> None:
    """Extract vendor name tokens from remaining text after all other fields removed."""
    # Remove "and" between amounts (artifact from multi-amount parsing)
    text = re.sub(r"\band\b", " ", text, flags=re.IGNORECASE)

    # Remove common noise words and punctuation
    noise = config.NOISE_WORDS

    # Tokenize: split on non-alphanumeric (keep hyphens for names like Pot-O-Gold)
    tokens = re.findall(r"[a-zA-Z][\w-]*", text)

    vendor_tokens = []
    for token in tokens:
        lower = token.lower()
        if lower not in noise and len(lower) > 0:
            vendor_tokens.append(lower)

    record.vendor_tokens = vendor_tokens
