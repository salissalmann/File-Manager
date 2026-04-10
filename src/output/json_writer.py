"""Serialize match results and ledger/file lists to JSON for the web UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.engine.explainer import explain, explain_ambiguity, format_signals
from src.models import FileRecord, LedgerRow, MatchResult, ScoredCandidate


def _ledger_row_dict(row: LedgerRow) -> dict[str, Any]:
    return {
        "index": row.index,
        "vendor": row.vendor,
        "date": row.date.isoformat(),
        "caCode": row.ca_code,
        "folder": row.folder,
        "amount": str(row.amount),
    }


def _file_record_dict(fr: FileRecord) -> dict[str, Any]:
    return {
        "originalName": fr.original_name,
        "vendorName": fr.vendor_name,
        "vendorTokens": fr.vendor_tokens,
        "caCodes": fr.ca_codes,
        "amounts": [str(a) for a in fr.amounts],
        "dates": [d.isoformat() for d in fr.dates],
        "invoiceNumbers": fr.invoice_numbers,
        "jobNumbers": fr.job_numbers,
    }


def _scored_candidate_dict(c: ScoredCandidate) -> dict[str, Any]:
    return {
        "file": _file_record_dict(c.file),
        "score": round(c.score, 2),
        "reasons": list(c.reasons),
        "vetoed": c.vetoed,
        "vetoReason": c.veto_reason,
    }


def _match_result_dict(
    r: MatchResult,
    path_by_filename: dict[str, str],
    file_link_base: str,
) -> dict[str, Any]:
    matched = r.matched_file
    fname = matched.original_name if matched else None
    path_from_root = path_by_filename.get(fname, "") if fname else ""
    link = ""
    if fname and file_link_base:
        base = file_link_base.rstrip("/")
        rel = path_from_root or fname
        link = f"{base}/{rel}"

    decision_trail = r.match_reason_str
    amb = explain_ambiguity(r)
    if amb:
        decision_trail = f"{decision_trail}\n{amb}"

    veto_info = ""
    if r.vetoed_candidates:
        top = r.vetoed_candidates[0]
        veto_info = f"{top.file.original_name}: {top.veto_reason or ''}"

    alt_parts = []
    for alt in r.alternatives[:3]:
        alt_parts.append(
            f"{alt.file.original_name} (score={alt.score:.0f}, {' + '.join(alt.reasons)})"
        )

    return {
        "ledgerRow": _ledger_row_dict(r.ledger_row),
        "matchedFile": _file_record_dict(matched) if matched else None,
        "matchedPathFromRoot": path_from_root,
        "fileLink": link,
        "score": round(r.score, 2),
        "reasons": list(r.reasons),
        "signals": format_signals(r),
        "status": r.status,
        "explanation": explain(r),
        "decisionTrail": decision_trail,
        "vetoInfo": veto_info,
        "alternatives": [_scored_candidate_dict(a) for a in r.alternatives[:3]],
        "isAmbiguous": r.is_ambiguous,
        "signalCount": r.signal_count,
    }


def build_web_state(
    ledger_rows: list[LedgerRow],
    file_inventory: list[dict[str, str]],
    results: list[MatchResult],
    orphans: list[FileRecord],
    file_link_base: str = "",
) -> dict[str, Any]:
    """Build the JSON object consumed by the Next.js app.

    file_inventory: rows with keys 'filename', 'pathFromRoot' (from Dropbox CSV).
    """
    path_by_filename: dict[str, str] = {}
    for row in file_inventory:
        fn = row.get("filename", "").strip()
        p = row.get("pathFromRoot", "").strip()
        if fn and fn not in path_by_filename:
            path_by_filename[fn] = p

    veto_log: list[dict[str, Any]] = []
    for r in results:
        for vc in r.vetoed_candidates:
            veto_log.append({
                "ledgerRowIndex": r.ledger_row.index,
                "ledgerVendor": r.ledger_row.vendor,
                "ledgerCa": r.ledger_row.ca_code,
                "ledgerAmount": str(r.ledger_row.amount),
                "rejectedFile": vc.file.original_name,
                "fileScore": round(vc.score, 2),
                "vetoReason": vc.veto_reason or "",
            })

    metrics = _compute_metrics(results, orphans)

    return {
        "version": 1,
        "ledgerRows": [_ledger_row_dict(lr) for lr in ledger_rows],
        "files": file_inventory,
        "results": [_match_result_dict(r, path_by_filename, file_link_base) for r in results],
        "orphans": [_file_record_dict(o) for o in orphans],
        "vetoLog": veto_log,
        "metrics": metrics,
    }


def _compute_metrics(results: list[MatchResult], orphans: list[FileRecord]) -> dict[str, Any]:
    import config

    total = len(results)
    confident = sum(1 for r in results if r.status == config.TIER_CONFIDENT)
    probable = sum(1 for r in results if r.status == config.TIER_PROBABLE)
    possible = sum(1 for r in results if r.status == config.TIER_POSSIBLE)
    review = sum(1 for r in results if r.status == config.TIER_REVIEW)
    no_match = sum(1 for r in results if r.status == config.TIER_NO_MATCH)
    ambiguous = sum(1 for r in results if r.is_ambiguous)
    matched = confident + probable
    rate = f"{(matched / total * 100):.1f}%" if total else "0%"
    return {
        "totalLedgerRows": total,
        "confident": confident,
        "probable": probable,
        "possible": possible,
        "review": review,
        "noMatch": no_match,
        "ambiguous": ambiguous,
        "orphanFiles": len(orphans),
        "matchRate": rate,
    }


def write_web_state_json(
    state: dict[str, Any],
    output_path: str | Path,
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
