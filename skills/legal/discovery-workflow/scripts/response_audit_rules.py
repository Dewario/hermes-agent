"""Shared FRCP rule_id baselines for A* response-audit deepen (synthetic-safe)."""

from __future__ import annotations

from typing import Any


def baseline_rule_ids(
    request_type: str,
    *,
    status: str,
    classification: str | None = None,
    kind: str | None = None,
) -> list[str]:
    """Return pack-aligned procedural rule ids for a response-audit finding."""
    rtype = (request_type or "").lower()
    rules: list[str] = ["FRCP-26-b-1"]
    if rtype == "rfa":
        rules.append("FRCP-36-a-1")
        if classification in {"object_only"}:
            rules.append("FRCP-36-a-5")
        elif classification in {"lack_information"}:
            rules.extend(["FRCP-36-a-4", "FRCP-26-e"])
        else:
            rules.append("FRCP-36-a-4")
    elif rtype == "rog":
        rules.append("FRCP-33-a-1")
        if status == "needs_attorney_decision" or (kind and "object" in str(kind)):
            rules.append("FRCP-33-b")
        else:
            rules.append("FRCP-33-b")
    elif rtype == "rfp":
        rules.append("FRCP-34-a")
        if status in {"conflicts_with_record", "unsupported"}:
            rules.append("FRCP-34-b-2")
        else:
            rules.append("FRCP-34-b-2")
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for rid in rules:
        if rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out


def intersect_pack(
    rule_ids: list[str],
    available: set[str] | None,
) -> tuple[list[str], bool]:
    """Keep only pack-known ids. Returns (ids, needs_attorney_rule_confirm)."""
    if not available:
        return list(rule_ids), False
    kept = [rid for rid in rule_ids if rid in available]
    missing = [rid for rid in rule_ids if rid not in available]
    if missing and not kept:
        return [], True
    return kept or list(rule_ids), bool(missing)


def attach_rule_ids(
    row: dict[str, Any],
    *,
    request_type: str,
    available: set[str] | None = None,
) -> dict[str, Any]:
    ids = baseline_rule_ids(
        request_type,
        status=str(row.get("status") or ""),
        classification=row.get("classification"),
        kind=row.get("kind"),
    )
    kept, needs_confirm = intersect_pack(ids, available)
    row = dict(row)
    row["rule_ids"] = kept
    if needs_confirm:
        row["needs_attorney_rule_confirm"] = True
        note = str(row.get("notes") or "")
        extra = "Rule id(s) missing from pinned pack — needs_attorney_rule_confirm."
        row["notes"] = f"{note} {extra}".strip() if note else extra
    else:
        row.setdefault("needs_attorney_rule_confirm", False)
    return row
