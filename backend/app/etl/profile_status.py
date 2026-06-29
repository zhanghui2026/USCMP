"""
Profile status computation: determines profile_status, parsed_fields, missing_fields
based on which structured biographical fields are populated.

Used by both USCL and Wikipedia import pathways.
"""

from __future__ import annotations

from typing import Any

ALL_PROFILE_FIELDS = [
    "short_summary",
    "birth_date",
    "birth_place",
    "education",
    "occupations",
    "prior_positions",
    "employers",
    "military_service",
    "image_url",
]

STRUCTURED_FIELDS = [
    "education",
    "occupations",
    "prior_positions",
    "employers",
    "military_service",
    "birth_place",
    "image_url",
]


def compute_profile_status(profile_data: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Determine profile_status, parsed_fields, missing_fields from a profile dict.

    Returns:
        (profile_status, parsed_fields, missing_fields)

    Status rules:
    - available: has short_summary + birth_date + at least 2 structured fields (education/occupations/prior_positions)
    - partial: has birth_date + at least 1 structured field
    - summary_only: has short_summary or birth_date, but no structured fields
    - fetch_failed: Wikipedia API unreachable (only used when adapter returns None)
    - not_imported: no profile row exists
    """
    parsed: list[str] = []
    missing: list[str] = []

    data = profile_data

    # short_summary
    if data.get("short_summary"):
        parsed.append("short_summary")
    else:
        missing.append("short_summary")

    # birth_date
    if data.get("birth_date"):
        parsed.append("birth_date")
    else:
        missing.append("birth_date")

    # birth_place
    if data.get("birth_place"):
        parsed.append("birth_place")
    else:
        missing.append("birth_place")

    # education (non-empty list)
    edu = data.get("education", [])
    if edu and len(edu) > 0:
        parsed.append("education")
    else:
        missing.append("education")

    # occupations (non-empty list)
    occ = data.get("occupations", [])
    if occ and len(occ) > 0:
        parsed.append("occupations")
    else:
        missing.append("occupations")

    # prior_positions (non-empty list)
    pp = data.get("prior_positions", [])
    if pp and len(pp) > 0:
        parsed.append("prior_positions")
    else:
        missing.append("prior_positions")

    # employers (non-empty list)
    emp = data.get("employers", [])
    if emp and len(emp) > 0:
        parsed.append("employers")
    else:
        missing.append("employers")

    # military_service (non-empty list)
    ms = data.get("military_service", [])
    if ms and len(ms) > 0:
        parsed.append("military_service")
    else:
        missing.append("military_service")

    # image_url
    if data.get("image_url"):
        parsed.append("image_url")
    else:
        missing.append("image_url")

    structured_count = sum(1 for f in STRUCTURED_FIELDS if f in parsed)

    if structured_count >= 2 and "short_summary" in parsed and "birth_date" in parsed:
        status = "available"
    elif structured_count >= 1 and "birth_date" in parsed:
        status = "partial"
    else:
        status = "summary_only"

    return status, parsed, missing
