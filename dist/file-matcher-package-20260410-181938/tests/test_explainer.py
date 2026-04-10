"""Tests for the plain-English explainer module — uses real vendor data."""

from datetime import date
from decimal import Decimal

import pytest

from src.engine.explainer import explain, explain_ambiguity, format_signals
from src.models import FileRecord, LedgerRow, MatchResult, ScoredCandidate


def _lr(vendor="Deluxe", ca="65100", amount=394.55):
    return LedgerRow(
        index=1, vendor=vendor, date=date(2021, 11, 19),
        ca_code=ca, folder=None, amount=Decimal(str(amount)),
    )


def _fr(name="file.pdf", vendor_tokens=None, ca_codes=None, amounts=None):
    return FileRecord(
        original_name=name,
        vendor_tokens=vendor_tokens or [],
        ca_codes=ca_codes or [],
        amounts=[Decimal(str(a)) for a in amounts] if amounts else [],
    )


class TestExplainConfident:
    """Explanations for Confident matches (3 signals)."""

    def test_confident_has_all_three_signals(self):
        result = MatchResult(
            ledger_row=_lr("VYO STRUCTURAL", "50405", 17930),
            matched_file=_fr("vyo.pdf", ["vyo"], ["50405"], [17930]),
            score=100.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
            status="Confident",
        )
        text = explain(result)
        assert "Confident match" in text
        assert "$17,930" in text
        assert "50405" in text
        assert "VYO STRUCTURAL" in text

    def test_confident_mentions_exact_amount(self):
        result = MatchResult(
            ledger_row=_lr(amount=222.77),
            matched_file=_fr(amounts=[222.77], ca_codes=["50408"], vendor_tokens=["home", "depot"]),
            score=100.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
            status="Confident",
        )
        text = explain(result)
        assert "exactly" in text.lower() or "exact" in text.lower()


class TestExplainProbable:
    """Explanations for Probable matches (2 signals)."""

    def test_probable_amount_vendor_no_ca(self):
        result = MatchResult(
            ledger_row=_lr("HOME DEPOT", "50408", 222.77),
            matched_file=_fr("hd.pdf", ["home", "depost"], [], [222.77]),
            score=70.0,
            reasons=["amount_exact", "vendor_match"],
            status="Probable",
        )
        text = explain(result)
        assert "Probable match" in text
        assert "no CA code" in text.lower() or "no ca" in text.lower()

    def test_probable_ca_vendor_no_amount(self):
        result = MatchResult(
            ledger_row=_lr("LINC PLUMBING", "53608", 11566),
            matched_file=_fr("linc.pdf", ["linc", "plumbing"], ["53608"], []),
            score=55.0,
            reasons=["ca_match", "vendor_match"],
            status="Probable",
        )
        text = explain(result)
        assert "53608" in text
        assert "No amount" in text or "no amount" in text


class TestExplainReview:
    """Explanations for Review matches (vendor-only)."""

    def test_review_vendor_only(self):
        result = MatchResult(
            ledger_row=_lr("POT-O-GOLD", "50500", 208.89),
            matched_file=_fr("pog.pdf", ["pot-o-gold"], [], []),
            score=20.0,
            reasons=["vendor_match"],
            status="Review",
        )
        text = explain(result)
        assert "Review match" in text
        assert "POT-O-GOLD" in text


class TestExplainNoMatch:
    """Explanations for No Match rows."""

    def test_no_match_basic(self):
        result = MatchResult(
            ledger_row=_lr("TACOS CHALES", "53604", 132.61),
            matched_file=None,
            score=0.0,
            reasons=[],
            status="No Match",
        )
        text = explain(result)
        assert "No match" in text
        assert "TACOS CHALES" in text
        assert "$132" in text

    def test_no_match_with_vetoed_candidate(self):
        vetoed = ScoredCandidate(
            file=_fr("bad.pdf", ["mesken"], ["66800"], [9999]),
            score=50.0,
            reasons=["ca_match", "vendor_match"],
            vetoed=True,
            veto_reason="Amount conflict",
        )
        result = MatchResult(
            ledger_row=_lr("MESKEN", "66800", 3000),
            matched_file=None,
            score=0.0,
            reasons=[],
            status="No Match",
            vetoed_candidates=[vetoed],
        )
        text = explain(result)
        assert "rejected" in text.lower() or "bad.pdf" in text
        assert "Amount conflict" in text


class TestExplainNearAmount:
    """Explanations for near-amount matches."""

    def test_near_amount_shows_difference(self):
        result = MatchResult(
            ledger_row=_lr("TOTAL SURVEYORS", "54500", 447.50),
            matched_file=_fr("ts.pdf", ["total", "surveyor"], ["54500"], [448]),
            score=90.0,
            reasons=["amount_near", "ca_match", "vendor_match"],
            status="Probable",
        )
        text = explain(result)
        assert "near" in text.lower() or "within" in text.lower()


class TestExplainSumMatch:
    """Explanations for sum-match rows."""

    def test_sum_match_mentions_partial(self):
        result = MatchResult(
            ledger_row=_lr("MESKEN", "66800", 3000),
            matched_file=_fr("mesken.pdf", ["mesken"], ["66800"], [9000]),
            score=85.0,
            reasons=["amount_sum_match", "ca_match", "vendor_match"],
            status="Possible",
        )
        text = explain(result)
        assert "sum" in text.lower() or "partial" in text.lower()


class TestExplainAmbiguity:
    """Tests for ambiguity explanation."""

    def test_not_ambiguous_returns_empty(self):
        result = MatchResult(
            ledger_row=_lr(),
            matched_file=_fr(amounts=[394.55]),
            score=100.0,
            reasons=["amount_exact"],
            status="Confident",
            is_ambiguous=False,
        )
        assert explain_ambiguity(result) == ""

    def test_ambiguous_shows_candidates(self):
        alt = ScoredCandidate(
            file=_fr("alt.pdf", amounts=[394.55]),
            score=95.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
        )
        result = MatchResult(
            ledger_row=_lr(),
            matched_file=_fr("win.pdf", amounts=[394.55]),
            score=100.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
            status="Probable",
            is_ambiguous=True,
            alternatives=[alt],
        )
        text = explain_ambiguity(result)
        assert "AMBIGUOUS" in text
        assert "win.pdf" in text
        assert "alt.pdf" in text
        assert "competing" in text.lower() or "candidates" in text.lower()


class TestFormatSignals:
    """Tests for signal count formatting."""

    def test_three_signals(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=100.0,
            reasons=["amount_exact", "ca_match", "vendor_match"],
        )
        assert format_signals(result) == "3/3 (amount_exact + ca + vendor)"

    def test_two_signals_amount_vendor(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=70.0,
            reasons=["amount_exact", "vendor_match"],
        )
        text = format_signals(result)
        assert "2/3" in text
        assert "amount_exact" in text
        assert "vendor" in text

    def test_one_signal_vendor_only(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=20.0,
            reasons=["vendor_match"],
        )
        text = format_signals(result)
        assert "1/3" in text
        assert "vendor" in text

    def test_near_amount_signal(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=90.0,
            reasons=["amount_near", "ca_match", "vendor_match"],
        )
        text = format_signals(result)
        assert "amount_near" in text
        assert "3/3" in text

    def test_zero_signals(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=None, score=0.0, reasons=[],
        )
        assert format_signals(result) == "0/3"

    def test_vendor_partial_signal(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=50.0,
            reasons=["amount_exact", "vendor_partial"],
        )
        text = format_signals(result)
        assert "vendor_partial" in text
        assert "2/3" in text

    def test_sum_match_signal(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=85.0,
            reasons=["amount_sum_match", "ca_match"],
        )
        text = format_signals(result)
        assert "amount_sum" in text
        assert "2/3" in text

    def test_format_signals_deduplicates_amount(self):
        result = MatchResult(
            ledger_row=_lr(), matched_file=_fr(), score=100.0,
            reasons=["amount_exact", "amount_near", "ca_match"],
        )
        text = format_signals(result)
        assert "amount_exact" in text
        assert "amount_near" not in text
        assert "2/3" in text


class TestExplainerEdgeCases:
    """Specific edge cases for explanation text."""

    def test_near_amount_shows_actual_diff(self):
        result = MatchResult(
            ledger_row=_lr(amount=3000),
            matched_file=_fr(amounts=[3001.50]),
            score=90.0,
            reasons=["amount_near"],
            status="Possible",
        )
        text = explain(result)
        assert "$1.5" in text or "$1.50" in text

    def test_no_amounts_in_file_explanation(self):
        result = MatchResult(
            ledger_row=_lr(amount=3000),
            matched_file=_fr(amounts=[]),
            score=50.0,
            reasons=["ca_match", "vendor_match"],
            status="Probable",
        )
        text = explain(result)
        assert "No amount found in file" in text

    def test_vendor_partial_explanation(self):
        result = MatchResult(
            ledger_row=_lr(vendor="MESKEN"),
            matched_file=_fr(vendor_tokens=["mesk"]),
            score=50.0,
            reasons=["vendor_partial"],
            status="Review",
        )
        text = explain(result)
        assert "partially matches" in text

    def test_ca_mismatch_shows_both_codes(self):
        result = MatchResult(
            ledger_row=_lr(ca="50670"),
            matched_file=_fr(ca_codes=["65100"]),
            score=50.0,
            reasons=["amount_exact"],
            status="Possible",
        )
        text = explain(result)
        assert "50670" in text
        assert "65100" in text

    def test_ambiguity_with_3_competitors(self):
        alts = [
            ScoredCandidate(_fr("alt1.pdf"), 90, ["amount_exact"]),
            ScoredCandidate(_fr("alt2.pdf"), 85, ["amount_near"]),
            ScoredCandidate(_fr("alt3.pdf"), 80, ["vendor_match"]),
        ]
        result = MatchResult(
            ledger_row=_lr(),
            matched_file=_fr("win.pdf"),
            score=100,
            reasons=["amount_exact", "ca_match"],
            is_ambiguous=True,
            alternatives=alts,
        )
        text = explain_ambiguity(result)
        assert "AMBIGUOUS" in text
        assert "alt1.pdf" in text
        assert "alt2.pdf" in text
        assert "alt3.pdf" in text

    def test_no_match_no_veto_basic(self):
        result = MatchResult(
            ledger_row=_lr(),
            matched_file=None,
            score=0,
            reasons=[],
            status="No Match",
        )
        text = explain(result)
        assert "No match found" in text
