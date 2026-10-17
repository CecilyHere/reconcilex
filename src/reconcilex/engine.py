"""Bounded candidate graph; uncertainty never becomes an automatic match."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timezone

from .config import Settings, money_minor, money_text, settings_from_dict
from .models import Dataset, ReconcileError, Transaction


def reconcile(ledger: Dataset, bank: Dataset, settings: Settings | None = None) -> dict:
    """Reconcile validated datasets without mutating them or choosing among ties."""
    from . import __version__
    settings = settings_from_dict((settings or Settings()).normalized())
    left = sorted(ledger.transactions, key=lambda t: t.id)
    right = sorted(bank.transactions, key=lambda t: t.id)
    if len({t.id for t in left}) != len(left) or len({t.id for t in right}) != len(right):
        raise ReconcileError("dataset contains duplicate transaction IDs")
    scales = settings.currency_precision
    currencies = sorted({t.currency for t in left + right})
    try:
        tolerances = {c: money_minor(settings.amount_tolerance, scales[c]) for c in currencies}
    except (KeyError, ReconcileError) as exc:
        raise ReconcileError(f"currency or amount_tolerance precision is invalid: {exc}") from exc
    buckets = defaultdict(list)
    for j, transaction in enumerate(right):
        buckets[transaction.currency].append((transaction.amount_minor, j))
    indexed = {}
    for code, values in buckets.items():
        ordered = sorted(values)
        indexed[code] = ([amount for amount, _ in ordered], ordered)
    edges, by_left, by_right = [], defaultdict(list), defaultdict(list)
    comparisons = 0
    for i, ltx in enumerate(left):
        amounts, ordered = indexed.get(ltx.currency, ([], []))
        tolerance = tolerances[ltx.currency]
        start = bisect_left(amounts, ltx.amount_minor - tolerance)
        stop = bisect_right(amounts, ltx.amount_minor + tolerance)
        for position in range(start, stop):
            comparisons += 1
            if comparisons > settings.max_comparisons:
                raise ReconcileError("candidate comparison limit exceeded; narrow the amount tolerance or split inputs by period")
            _, j = ordered[position]
            rtx = right[j]
            if (ltx.amount_minor > 0) != (rtx.amount_minor > 0) or (ltx.amount_minor < 0) != (rtx.amount_minor < 0):
                continue
            if abs((ltx.date - rtx.date).days) > settings.date_window_days:
                continue
            if ltx.reference and rtx.reference and ltx.reference.casefold() != rtx.reference.casefold():
                continue
            if len(edges) >= settings.max_candidates:
                raise ReconcileError("candidate edge limit exceeded; narrow the date window/tolerance or split the inputs")
            edge = len(edges)
            edges.append((i, j))
            by_left[i].append(edge)
            by_right[j].append(edge)

    def row(tx: Transaction) -> dict:
        return {"id": tx.id, "date": tx.date.isoformat(), "amount": money_text(tx.amount_minor, scales[tx.currency]),
                "currency": tx.currency, "reference": tx.reference, "description": tx.description,
                "source_row": tx.row, "duplicate_content": tx.duplicate_content}

    matches, review = [], []
    used_left, used_right = set(), set()
    for i, j in edges:
        ltx, rtx = left[i], right[j]
        reasons = []
        if len(by_left[i]) != 1 or len(by_right[j]) != 1:
            reasons.append("ambiguous_candidates")
        if ltx.duplicate_content or rtx.duplicate_content:
            reasons.append("duplicate_content")
        if ltx.amount_minor != rtx.amount_minor:
            reasons.append("amount_difference")
        if ltx.amount_minor == 0 or rtx.amount_minor == 0:
            reasons.append("zero_amount")
        candidate = {"ledger_id": ltx.id, "bank_id": rtx.id, "currency": ltx.currency,
                     "ledger_date": ltx.date.isoformat(), "bank_date": rtx.date.isoformat(),
                     "ledger_source_row": ltx.row, "bank_source_row": rtx.row,
                     "ledger_reference": ltx.reference, "bank_reference": rtx.reference,
                     "ledger_amount": money_text(ltx.amount_minor, scales[ltx.currency]),
                     "bank_amount": money_text(rtx.amount_minor, scales[ltx.currency]),
                     "difference": money_text(ltx.amount_minor - rtx.amount_minor, scales[ltx.currency]),
                     "date_gap_days": abs((ltx.date - rtx.date).days),
                     "rule": "reference_amount_date" if ltx.reference and rtx.reference else "amount_date",
                     "reasons": reasons}
        if reasons:
            review.append(candidate)
        else:
            matches.append(candidate)
            used_left.add(i)
            used_right.add(j)
    remaining_left = [row(t) | {"reason": "review_candidates" if by_left[i] else "no_eligible_candidate"}
                      for i, t in enumerate(left) if i not in used_left]
    remaining_right = [row(t) | {"reason": "review_candidates" if by_right[j] else "no_eligible_candidate"}
                       for j, t in enumerate(right) if j not in used_right]
    totals = {}
    for code in currencies:
        ledger_total = sum(t.amount_minor for t in left if t.currency == code)
        bank_total = sum(t.amount_minor for t in right if t.currency == code)
        matched_ledger = sum(left[i].amount_minor for i in used_left if left[i].currency == code)
        matched_bank = sum(right[j].amount_minor for j in used_right if right[j].currency == code)
        matched_difference = matched_ledger - matched_bank
        remaining_difference = (ledger_total - matched_ledger) - (bank_total - matched_bank)
        if ledger_total - bank_total != matched_difference + remaining_difference:
            raise ReconcileError("internal conservation invariant failed")
        values = {"ledger_total": ledger_total, "bank_total": bank_total,
                  "input_difference": ledger_total - bank_total, "matched_difference": matched_difference,
                  "remaining_difference": remaining_difference}
        totals[code] = {key: money_text(value, scales[code]) for key, value in values.items()} | {"conservation_passed": True}
    return {"schema_version": 1, "app_version": __version__,
            "created_at": datetime.now(timezone.utc).isoformat(), "config": settings.normalized(),
            "inputs": {"ledger": {"filename": ledger.filename, "sha256": ledger.sha256},
                       "bank": {"filename": bank.filename, "sha256": bank.sha256}},
            "summary": {"ledger_rows": len(left), "bank_rows": len(right), "matched_pairs": len(matches),
                        "review_candidates": len(review), "remaining_ledger": len(remaining_left),
                        "remaining_bank": len(remaining_right), "candidate_comparisons": comparisons},
            "totals": totals, "matches": matches, "review_candidates": review,
            "remaining_ledger": remaining_left, "remaining_bank": remaining_right,
            "warnings": {"ledger": list(ledger.warnings), "bank": list(bank.warnings)}}
