"""Matcher orchestrator — scores all pairs, applies veto, assigns 1:1, classifies."""

from __future__ import annotations

from decimal import Decimal
from itertools import combinations

import config
from src.engine.scorer import score_pair, _amounts_within_tolerance, get_vendor_similarity
from src.engine.veto import apply_veto_rules, apply_veto_rules_sum_match
from src.models import FileRecord, LedgerRow, MatchResult, ScoredCandidate
from src.parsers.filename_parser import parse_filename


def run_matching(
    ledger_rows: list[LedgerRow],
    filenames: list[str],
) -> tuple[list[MatchResult], list[FileRecord]]:
    """Run the full matching pipeline.

    Returns:
        (match_results, orphan_files) — results for each ledger row,
        plus files that matched nothing.
    """
    # Step 1: Parse all filenames, assign unique index to each
    file_records = [parse_filename(fn) for fn in filenames]

    # Step 2: Score all (ledger, file) pairs and apply veto rules
    candidate_matrix: dict[int, list[tuple[int, ScoredCandidate]]] = {}
    for row in ledger_rows:
        candidates = []
        for fi, fr in enumerate(file_records):
            candidate = score_pair(row, fr)
            candidate = apply_veto_rules(row, candidate)
            candidates.append((fi, candidate))
        candidates.sort(key=lambda x: (not x[1].vetoed, x[1].score), reverse=True)
        candidate_matrix[row.index] = candidates

    # Step 3: Greedy 1:1 assignment
    assignments: list[tuple[int, int, float, ScoredCandidate]] = []
    for row_idx, candidates in candidate_matrix.items():
        for fi, c in candidates:
            if not c.vetoed and c.score > 0:
                assignments.append((row_idx, fi, c.score, c))

    assignments.sort(key=lambda x: x[2], reverse=True)

    assigned_file_counts: dict[int, int] = {}
    assigned_rows: set[int] = set()
    row_to_match: dict[int, ScoredCandidate] = {}
    row_to_file_idx: dict[int, int] = {}

    for row_idx, fi, score, candidate in assignments:
        if row_idx in assigned_rows:
            continue

        file = candidate.file
        current_count = assigned_file_counts.get(fi, 0)
        max_assignments = max(len(file.amounts), 1)

        if current_count < max_assignments:
            row_to_match[row_idx] = candidate
            row_to_file_idx[row_idx] = fi
            assigned_rows.add(row_idx)
            assigned_file_counts[fi] = current_count + 1

    # Step 4: Partial payment sum matching (second pass)
    # For unmatched rows, check if multiple ledger amounts sum to a file amount
    _partial_payment_pass(
        ledger_rows, file_records, candidate_matrix,
        assigned_rows, row_to_match, row_to_file_idx, assigned_file_counts,
    )

    # Step 5: Build MatchResults
    results: list[MatchResult] = []
    matched_file_indices: set[int] = set()

    for row in ledger_rows:
        candidates_with_idx = candidate_matrix[row.index]
        candidates = [c for _, c in candidates_with_idx]
        vetoed = [c for c in candidates if c.vetoed and c.score > 0]

        # Collect top non-vetoed alternatives (for Review rows)
        alternatives = [
            c for c in candidates
            if not c.vetoed and c.score > 0
            and (row.index not in row_to_match or c.file.original_name != row_to_match[row.index].file.original_name)
        ][:3]

        if row.index in row_to_match:
            match = row_to_match[row.index]
            ambiguous = _is_ambiguous(match, candidates)
            status = _classify(match, candidates, ambiguous, ledger_row=row)
            matched_file_indices.add(row_to_file_idx[row.index])
            results.append(MatchResult(
                ledger_row=row,
                matched_file=match.file,
                score=match.score,
                reasons=match.reasons,
                status=status,
                vetoed_candidates=vetoed,
                all_candidates=candidates,
                alternatives=alternatives,
                is_ambiguous=ambiguous,
            ))
        else:
            results.append(MatchResult(
                ledger_row=row,
                matched_file=None,
                score=0.0,
                reasons=[],
                status=config.TIER_NO_MATCH,
                vetoed_candidates=vetoed,
                all_candidates=candidates,
                alternatives=alternatives,
            ))

    # Step 6: Identify orphan files
    orphans = [
        file_records[i] for i in range(len(file_records))
        if i not in matched_file_indices
    ]

    return results, orphans


def _partial_payment_pass(
    ledger_rows: list[LedgerRow],
    file_records: list[FileRecord],
    candidate_matrix: dict[int, list[tuple[int, ScoredCandidate]]],
    assigned_rows: set[int],
    row_to_match: dict[int, ScoredCandidate],
    row_to_file_idx: dict[int, int],
    assigned_file_counts: dict[int, int],
) -> None:
    """Second pass: check if unmatched rows can be linked via partial payment sums.

    If two or more unmatched ledger rows share the same vendor + CA, and their
    amounts sum to an amount found in a file, link them to that file.
    """
    unmatched = [r for r in ledger_rows if r.index not in assigned_rows]
    if not unmatched:
        return

    # Group unmatched rows by (vendor_lower, ca_code)
    groups: dict[tuple[str, str], list[LedgerRow]] = {}
    for row in unmatched:
        key = (row.vendor.lower().strip(), row.ca_code)
        groups.setdefault(key, []).append(row)

    for (vendor_key, ca_key), rows in groups.items():
        if len(rows) < 2:
            continue

        # Try all pairs of unmatched rows in this group
        for r1, r2 in combinations(rows, 2):
            if r1.index in assigned_rows or r2.index in assigned_rows:
                continue

            combined = r1.amount + r2.amount

            # Find a file that has this combined amount + matching vendor/CA
            for fi, fr in enumerate(file_records):
                if fi in assigned_file_counts and assigned_file_counts[fi] >= max(len(fr.amounts), 1):
                    continue

                has_amount = any(
                    fa == combined or _amounts_within_tolerance(fa, combined)
                    for fa in fr.amounts
                )
                has_ca = ca_key in fr.ca_codes if fr.ca_codes else True
                has_vendor = (
                    get_vendor_similarity(vendor_key, fr.vendor_tokens) >= config.VENDOR_PARTIAL_THRESHOLD
                    if fr.vendor_tokens else True
                )

                if has_amount and has_ca and has_vendor:
                    # Build reasons and score from only the signals that actually fired
                    score = config.AMOUNT_SUM_WEIGHT
                    reasons = ["amount_sum_match"]
                    if ca_key in fr.ca_codes:
                        score += config.CA_MATCH_WEIGHT
                        reasons.append("ca_match")
                    if fr.vendor_tokens and has_vendor:
                        score += config.VENDOR_STRONG_WEIGHT
                        reasons.append("vendor_match")

                    # Create sum-match candidates for both rows and apply veto rules
                    # (uses sum-match variant that skips amount conflict veto, since
                    # individual row amounts intentionally don't equal the file amount)
                    for row in (r1, r2):
                        sc = ScoredCandidate(file=fr, score=score, reasons=reasons)
                        sc = apply_veto_rules_sum_match(row, sc)
                        if sc.vetoed:
                            break
                        row_to_match[row.index] = sc
                        row_to_file_idx[row.index] = fi
                        assigned_rows.add(row.index)
                    else:

                        assigned_file_counts[fi] = assigned_file_counts.get(fi, 0) + 2
                        break


def _classify(
    candidate: ScoredCandidate,
    all_candidates: list[ScoredCandidate],
    is_ambiguous: bool,
    ledger_row: LedgerRow | None = None,
) -> str:
    """Classify match into 5 tiers based on signal count + quality."""
    reasons = set(candidate.reasons)

    has_amount = bool(reasons & {"amount_exact", "amount_near", "amount_sum_match"})
    has_amount_direct = bool(reasons & {"amount_exact", "amount_near"})
    has_ca = "ca_match" in reasons
    has_vendor = bool(reasons & {"vendor_match", "vendor_partial"})
    has_vendor_strong = "vendor_match" in reasons

    signal_count = sum([has_amount, has_ca, has_vendor])

    # Conservative cap: if the ledger row has a known vendor but the file has
    # no parseable vendor tokens, we cannot confirm vendor identity.  Cap at
    # Possible — never Probable or Confident — to surface these for review.
    vendor_unverifiable = (
        ledger_row is not None
        and ledger_row.vendor
        and not candidate.file.vendor_tokens
    )

    # Vendor-only cap: always Review
    if has_vendor and not has_amount and not has_ca:
        return config.TIER_REVIEW

    # 3 signals — Confident requires exact amount, never amount_near alone
    if signal_count == 3:
        if "amount_exact" in reasons and not is_ambiguous:
            return config.TIER_CONFIDENT if not vendor_unverifiable else config.TIER_POSSIBLE
        if is_ambiguous:
            return config.TIER_PROBABLE if not vendor_unverifiable else config.TIER_POSSIBLE
        if has_amount_direct:
            return config.TIER_PROBABLE if not vendor_unverifiable else config.TIER_POSSIBLE
        # amount_sum_match with 3 signals → Possible (needs verification)
        return config.TIER_POSSIBLE

    # 2 signals
    if signal_count == 2:
        if is_ambiguous:
            return config.TIER_POSSIBLE
        if has_amount_direct:
            return config.TIER_PROBABLE if not vendor_unverifiable else config.TIER_POSSIBLE
        if has_ca and has_vendor_strong:
            return config.TIER_PROBABLE if not vendor_unverifiable else config.TIER_POSSIBLE
        return config.TIER_POSSIBLE

    # 1 signal
    if signal_count == 1:
        if has_amount_direct:
            return config.TIER_POSSIBLE
        return config.TIER_REVIEW

    return config.TIER_NO_MATCH


def _is_ambiguous(
    winner: ScoredCandidate,
    all_candidates: list[ScoredCandidate],
) -> bool:
    """Detect if winner has a near-tie competitor.

    Returns True if any non-vetoed candidate (other than winner) has a score
    within AMBIGUITY_SCORE_GAP of the winner AND has at least 1 core signal.
    """
    for c in all_candidates:
        if c.vetoed or c.score == 0:
            continue
        if c.file.original_name == winner.file.original_name:
            continue
        score_gap = winner.score - c.score
        if score_gap < config.AMBIGUITY_SCORE_GAP:
            # Competitor must have at least one core signal
            c_reasons = set(c.reasons)
            c_has_signal = bool(
                c_reasons & {"amount_exact", "amount_near", "amount_sum_match"}
                or "ca_match" in c_reasons
                or c_reasons & {"vendor_match", "vendor_partial"}
            )
            if c_has_signal:
                return True
    return False
