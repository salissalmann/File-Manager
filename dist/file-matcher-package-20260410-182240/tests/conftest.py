"""Shared fixtures and factories for the test suite.

Uses real data: Milford-Ledger Clean.xlsx (788 rows) + dropbox_files.csv (934 files).
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal

import pytest

from src.engine.matcher import run_matching
from src.models import FileRecord, LedgerRow
from src.parsers.ledger_parser import parse_ledger


LEDGER_PATH = "inputs/Milford-Ledger Clean.xlsx"
DROPBOX_CSV_PATH = "inputs/dropbox_files.csv"


# ── Session-scoped fixtures (run once per test session) ──────────────


@pytest.fixture(scope="session")
def real_ledger_rows():
    """Parse the real Milford ledger once for the entire test session."""
    return parse_ledger(LEDGER_PATH)


@pytest.fixture(scope="session")
def real_filenames():
    """Load real Dropbox filenames once for the entire test session."""
    filenames = []
    with open(DROPBOX_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Filename", "").strip()
            if name:
                filenames.append(name)
    return filenames


@pytest.fixture(scope="session")
def full_match_results(real_ledger_rows, real_filenames):
    """Run the full matching pipeline once for the entire test session."""
    return run_matching(real_ledger_rows, real_filenames)


# ── Factory helpers ──────────────────────────────────────────────────


def make_ledger(index=1, vendor="Deluxe", ca="65100", amount="394.55",
                dt="2021-11-19"):
    """Create a LedgerRow with real-world defaults."""
    return LedgerRow(
        index=index, vendor=vendor, date=date.fromisoformat(dt),
        ca_code=ca, folder=None, amount=Decimal(amount),
    )


def make_file(name="test.pdf", vendor_tokens=None, ca_codes=None,
              amounts=None, invoice_numbers=None):
    """Create a FileRecord with empty defaults."""
    return FileRecord(
        original_name=name,
        vendor_tokens=vendor_tokens or [],
        ca_codes=ca_codes or [],
        amounts=[Decimal(a) for a in (amounts or [])],
        invoice_numbers=invoice_numbers or [],
    )
