"""Shared jurisdiction numerical-limit resolvers for discovery.

Used by both incoming request auditors and outgoing drafters so plaintiff-side
propounding and defense-served auditing apply the same jurisdiction-aware caps.

WA CR 33 has no statewide interrogatory cap. Local limits are county-specific:
King LCR 26 caps interrogatories at 40 unless court-approved pattern
interrogatories apply; Pierce PCLR 3(h) is track-dependent. California caps
specially prepared interrogatories at 35 under CCP 2030.030. Federal Rule 33
caps interrogatories at 25.

Synthetic-only until owner section 9.5; these resolvers are deterministic and
do not render legal conclusions.
"""

from __future__ import annotations

from typing import Any


DEFAULT_ROG_LIMIT = 25
CA_RFA_LIMIT = 35

PIERCE_TRACK_ROG_LIMITS = {
    "expedited": 25,
    "standard": 35,
    "complex": 35,
    "dissolution": 100,
}

WA_BASE_PACKS = {"wa_state", "wa_cr"}
WA_KING_OVERLAYS = {"wa_king_county", "wa_king_lcr"}
WA_PIERCE_OVERLAYS = {"wa_pierce_county", "wa_pierce_pclr"}


def _positive_int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _explicit_limit(raw: dict[str, Any], key: str) -> int | None:
    direct = _positive_int(raw.get(f"{key}_limit"))
    if direct is not None:
        return direct
    numerical = raw.get("numerical_limits") or {}
    if isinstance(numerical, dict):
        return _positive_int(numerical.get(key))
    return None


def resolve_rog_limit(profile: dict[str, Any], available_rules: set[str]) -> int | None:
    """Resolve the interrogatory numerical limit for a matter.

    Returns an integer cap, or None when the governing cap is not determinable
    from the selected pack/overlay and should be supplied or confirmed by an
    attorney in the matter profile.
    """

    raw = profile.get("raw") or {}
    pack = str(profile.get("jurisdiction_pack") or "")
    overlay = str(profile.get("case_overlay") or "")

    explicit = _explicit_limit(raw, "rog")
    if explicit is not None:
        return explicit

    if "CCP-2030-030" in available_rules:
        return 35

    if pack in WA_BASE_PACKS:
        if overlay in WA_KING_OVERLAYS:
            return 40
        if overlay in WA_PIERCE_OVERLAYS:
            track = str(raw.get("track") or "").strip().lower()
            return PIERCE_TRACK_ROG_LIMITS.get(track)
        return None

    return DEFAULT_ROG_LIMIT


def resolve_rfa_limit(profile: dict[str, Any], available_rules: set[str]) -> int | None:
    """Resolve the request-for-admission numerical limit for a matter.

    California caps non-genuineness RFAs at 35. King County caps RFAs at 25 per
    party under LCR 26(b)(2)(4), excluding RFAs propounded solely to authenticate
    documents. Washington statewide, Pierce County, and federal practice impose
    no numerical RFA cap in the sources verified for this iteration.
    """

    raw = profile.get("raw") or {}
    pack = str(profile.get("jurisdiction_pack") or "")
    overlay = str(profile.get("case_overlay") or "")

    explicit = _explicit_limit(raw, "rfa")
    if explicit is not None:
        return explicit

    if "CCP-2033-030" in available_rules:
        return CA_RFA_LIMIT

    if pack in WA_BASE_PACKS:
        if overlay in WA_KING_OVERLAYS:
            return 25
        return None

    return None


def resolve_rfp_limit(profile: dict[str, Any], available_rules: set[str]) -> int | None:
    """Resolve the request-for-production numerical limit for a matter.

    No verified covered jurisdiction imposes a numerical cap on RFP count.
    Attorney-supplied overrides are honored for case-specific orders.
    """

    raw = profile.get("raw") or {}
    return _explicit_limit(raw, "rfp")
