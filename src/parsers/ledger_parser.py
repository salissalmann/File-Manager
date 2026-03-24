"""Parse ledger Excel files into structured LedgerRow objects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

from src.models import LedgerRow


def parse_ledger(file_path: str | Path) -> list[LedgerRow]:
    """Read a ledger Excel file and return a list of LedgerRow objects.

    Expects columns: Vendor, Date, CA Account, Folder, Amount
    Skips the header row and any empty rows.
    """
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows: list[LedgerRow] = []

    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Skip empty rows
        if not row or row[0] is None:
            continue

        vendor = _normalize_vendor(row[0])
        dt = _parse_date(row[1])
        ca_code = _normalize_ca(row[2])
        folder = str(row[3]).strip() if row[3] else None
        amount = _parse_amount(row[4])

        if vendor and dt and amount is not None:
            rows.append(LedgerRow(
                index=idx - 1,  # 1-based data row index
                vendor=vendor,
                date=dt,
                ca_code=ca_code,
                folder=folder,
                amount=amount,
            ))

    wb.close()
    return rows


def _normalize_vendor(value: object) -> str:
    """Normalize vendor name: strip whitespace, preserve original case."""
    return str(value).strip()


def _parse_date(value: object) -> date | None:
    """Parse a date from Excel cell (may be datetime or string)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _normalize_ca(value: object) -> str:
    """Normalize CA code: convert to string, strip whitespace."""
    if value is None:
        return ""
    # Handle numeric CA codes (Excel may store as int/float)
    if isinstance(value, (int, float)):
        return str(int(value))
    return str(value).strip()


def _parse_amount(value: object) -> Decimal | None:
    """Parse amount from Excel cell."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "")
        try:
            return Decimal(cleaned)
        except Exception:
            return None
    return None
