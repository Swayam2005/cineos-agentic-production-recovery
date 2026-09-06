"""
CineOS production tools.

These tools provide structured production facts for the hackathon demo.

DATE BEHAVIOR
-------------
The production scenario is relative to the day the application runs.

Today:
    date.today()

Tomorrow:
    date.today() + 1 day

The demo incident is intentionally modeled as:

    Maya Chen is unavailable tomorrow.
    Scene 42 requires Maya Chen.
    Scene 47 does not require Maya Chen.
    Elias is available tomorrow.
    Nora is available tomorrow.
    Studio A is reserved tomorrow.
    Dock Set is available tomorrow.

This keeps the scenario deterministic while allowing the calendar date
to move automatically.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


# ============================================================================
# DYNAMIC PRODUCTION CLOCK
# ============================================================================


def get_today() -> str:
    """Return today's real calendar date as ISO YYYY-MM-DD."""
    return date.today().isoformat()


def get_tomorrow() -> str:
    """Return tomorrow's real calendar date as ISO YYYY-MM-DD."""
    return (date.today() + timedelta(days=1)).isoformat()


def get_demo_date() -> dict[str, str]:
    """
    Return the current CineOS production clock.

    The hackathon scenario intentionally follows the machine's current
    calendar date so that 'today' and 'tomorrow' remain correct whenever
    the application is run.
    """

    return {
        "today": get_today(),
        "tomorrow": get_tomorrow(),
        "source": "system_calendar",
    }


def resolve_production_date(
    production_date: str | None = None,
) -> str:
    """
    Resolve a production date.

    Supported values:

        None / empty -> tomorrow
        "today"      -> today
        "tomorrow"   -> tomorrow
        "demo"       -> tomorrow
        explicit ISO date -> that exact date

    Why default to tomorrow?

    The main CineOS incident concerns recovering production for the
    affected shooting date, which is "tomorrow" in the producer request.

    Explicit dates are preserved exactly and are never silently changed.
    """

    if production_date is None:
        return get_tomorrow()

    value = str(production_date).strip()

    if not value:
        return get_tomorrow()

    normalized = value.lower()

    if normalized == "today":
        return get_today()

    if normalized == "tomorrow":
        return get_tomorrow()

    if normalized == "demo":
        return get_tomorrow()

    return value


# ============================================================================
# PRODUCTION SCENES
# ============================================================================

SCENES: dict[str, dict[str, Any]] = {
    "42": {
        "scene_id": "42",
        "title": "The Signal Room",
        "characters": [
            "Maya Chen",
            "Elias",
        ],
        "location": "Studio A",
        "day": 24,
        "duration_minutes": 18,
        "equipment": [
            "Camera Package B",
            "Rain FX",
        ],
        "dependencies": [
            "41",
            "43",
        ],
    },
    "47": {
        "scene_id": "47",
        "title": "Night Crossing",
        "characters": [
            "Elias",
            "Nora",
        ],
        "location": "Dock Set",
        "day": 24,
        "duration_minutes": 12,
        "equipment": [
            "Camera Package A",
        ],
        "dependencies": [
            "46",
        ],
    },
}


# ============================================================================
# ACTOR AVAILABILITY
# ============================================================================
#
# The important demo behavior is relative to the current run:
#
#   today:
#       Maya Chen -> available
#
#   tomorrow:
#       Maya Chen -> unavailable
#       Elias     -> available
#       Nora      -> available
#
# This means the system can be run on any calendar date without becoming
# dependent on stale hard-coded dates.
# ============================================================================


ACTOR_AVAILABILITY: dict[str, dict[str, str]] = {
    "Maya Chen": {
        "today": "available",
        "tomorrow": "unavailable",
    },
    "Elias": {
        "today": "available",
        "tomorrow": "available",
    },
    "Nora": {
        "today": "available",
        "tomorrow": "available",
    },
}


# ============================================================================
# LOCATION AVAILABILITY
# ============================================================================
#
# Tomorrow:
#
#   Studio A -> reserved
#   Dock Set  -> available
#
# This supports the Scene 42 -> Scene 47 recovery validation.
# ============================================================================


LOCATION_AVAILABILITY: dict[str, dict[str, str]] = {
    "Studio A": {
        "today": "reserved",
        "tomorrow": "reserved",
    },
    "Dock Set": {
        "today": "available",
        "tomorrow": "available",
    },
}


# ============================================================================
# HELPERS
# ============================================================================


def _normalize_scene_id(scene_id: str) -> str:
    """
    Normalize scene identifiers.

    Accepted examples:

        "42"
        "Scene 42"
        "scene 42"
        " SCENE 42 "
    """

    value = str(scene_id).strip()

    if value.lower().startswith("scene "):
        value = value[6:].strip()

    return value


def _date_key(production_date: str) -> str | None:
    """
    Convert an actual ISO date into the relative demo key.

    Returns:

        "today"
        "tomorrow"
        None

    This is what allows the fixture to move with the calendar.
    """

    today = get_today()
    tomorrow = get_tomorrow()

    if production_date == today:
        return "today"

    if production_date == tomorrow:
        return "tomorrow"

    return None


# ============================================================================
# SCENE LOOKUP
# ============================================================================


def get_scene(scene_id: str) -> dict:
    """
    Return structured production data for a scene.
    """

    requested_id = str(scene_id).strip()
    normalized_id = _normalize_scene_id(requested_id)

    scene = SCENES.get(normalized_id)

    if scene is not None:
        return dict(scene)

    # Defensive compatibility if a future dataset uses
    # "Scene 42" as a dictionary key.
    scene = SCENES.get(
        f"Scene {normalized_id}"
    )

    if scene is not None:
        return dict(scene)

    return {
        "error": f"Scene {normalized_id} not found",
        "requested_scene_id": requested_id,
        "available_scene_ids": sorted(SCENES.keys()),
    }


# ============================================================================
# ACTOR AVAILABILITY
# ============================================================================


def get_actor_availability(
    actor: str,
    date: str | None = None,
) -> dict:
    """
    Return actor availability for a production date.

    Examples:

        get_actor_availability("Maya Chen")

        get_actor_availability(
            "Maya Chen",
            "tomorrow",
        )

        get_actor_availability(
            "Maya Chen",
            "today",
        )

        get_actor_availability(
            "Maya Chen",
            "2026-09-01",
        )

    Unknown dates remain "unknown".
    """

    actor_name = str(actor).strip()

    date_value = resolve_production_date(date)

    relative_key = _date_key(date_value)

    if relative_key is None:
        status = "unknown"
    else:
        status = ACTOR_AVAILABILITY.get(
            actor_name,
            {},
        ).get(
            relative_key,
            "unknown",
        )

    return {
        "actor": actor_name,
        "date": date_value,
        "status": status,
        "date_context": relative_key or "explicit_date",
        "today": get_today(),
        "tomorrow": get_tomorrow(),
    }


# ============================================================================
# LOCATION SCHEDULE
# ============================================================================


def get_location_schedule(
    location: str,
    date: str | None = None,
) -> dict:
    """
    Return location availability for a production date.

    Unknown dates remain "unknown".
    """

    location_name = str(location).strip()

    date_value = resolve_production_date(date)

    relative_key = _date_key(date_value)

    if relative_key is None:
        status = "unknown"
    else:
        status = LOCATION_AVAILABILITY.get(
            location_name,
            {},
        ).get(
            relative_key,
            "unknown",
        )

    return {
        "location": location_name,
        "date": date_value,
        "status": status,
        "date_context": relative_key or "explicit_date",
        "today": get_today(),
        "tomorrow": get_tomorrow(),
    }


# ============================================================================
# SWAP VALIDATION
# ============================================================================


def validate_swap_candidate(
    affected_scene: str,
    replacement_scene: str,
    date: str | None = None,
) -> dict:
    """
    Verify whether a replacement scene can safely be used.

    A replacement is feasible only when:

    1. Both scenes exist.
    2. Maya Chen is not required by the replacement.
    3. Every replacement cast member is explicitly available.
    4. The replacement location is explicitly available.

    Unknown availability is NOT treated as available.
    """

    affected_id = _normalize_scene_id(
        affected_scene
    )

    replacement_id = _normalize_scene_id(
        replacement_scene
    )

    date_value = resolve_production_date(date)

    affected = SCENES.get(affected_id)
    replacement = SCENES.get(replacement_id)

    # ------------------------------------------------------------------
    # Affected scene must exist.
    # ------------------------------------------------------------------

    if affected is None:
        return {
            "feasible": False,
            "reason": (
                f"Affected scene {affected_id} "
                "not found."
            ),
            "affected_scene": affected_id,
            "replacement_scene": replacement_id,
            "date": date_value,
        }

    # ------------------------------------------------------------------
    # Replacement scene must exist.
    # ------------------------------------------------------------------

    if replacement is None:
        return {
            "feasible": False,
            "reason": (
                f"Replacement scene {replacement_id} "
                "not found."
            ),
            "affected_scene": affected_id,
            "replacement_scene": replacement_id,
            "date": date_value,
        }

    replacement_characters = replacement.get(
        "characters",
        [],
    )

    # ------------------------------------------------------------------
    # Maya cannot appear in replacement scene.
    # ------------------------------------------------------------------

    maya_required = (
        "Maya Chen" in replacement_characters
    )

    if maya_required:
        return {
            "feasible": False,
            "reason": (
                f"Scene {replacement_id} requires Maya Chen, "
                f"who is unavailable on {date_value}."
            ),
            "affected_scene": affected_id,
            "replacement_scene": replacement_id,
            "date": date_value,
            "replacement_title": replacement.get(
                "title"
            ),
            "replacement_characters": (
                replacement_characters
            ),
            "replacement_location": replacement.get(
                "location"
            ),
            "maya_required": True,
        }

    # ------------------------------------------------------------------
    # Verify replacement location.
    # ------------------------------------------------------------------

    location_name = replacement.get(
        "location",
        "",
    )

    location_result = get_location_schedule(
        location_name,
        date_value,
    )

    # ------------------------------------------------------------------
    # Verify every replacement cast member.
    # ------------------------------------------------------------------

    cast_results: list[dict[str, Any]] = []

    unknown_cast: list[str] = []

    unavailable_cast: list[str] = []

    for actor in replacement_characters:

        result = get_actor_availability(
            actor,
            date_value,
        )

        cast_results.append(result)

        if result["status"] == "unknown":
            unknown_cast.append(actor)

        elif result["status"] == "unavailable":
            unavailable_cast.append(actor)

    # ------------------------------------------------------------------
    # Location is not available.
    # ------------------------------------------------------------------

    if location_result["status"] != "available":

        if location_result["status"] == "unknown":
            reason = (
                f"Replacement location "
                f"{location_name} is unknown on "
                f"{date_value}."
            )

        else:
            reason = (
                f"Replacement location "
                f"{location_name} is not available on "
                f"{date_value}: "
                f"{location_result['status']}."
            )

        if unknown_cast:
            reason += (
                " Replacement cast availability unknown: "
                + ", ".join(unknown_cast)
                + "."
            )

        if unavailable_cast:
            reason += (
                " Unavailable replacement cast: "
                + ", ".join(unavailable_cast)
                + "."
            )

        return {
            "feasible": False,
            "reason": reason,
            "affected_scene": affected_id,
            "replacement_scene": replacement_id,
            "date": date_value,
            "replacement_title": replacement.get(
                "title"
            ),
            "replacement_characters": (
                replacement_characters
            ),
            "replacement_location": location_name,
            "maya_required": False,
            "location": location_result,
            "cast": cast_results,
            "unknown_cast": unknown_cast,
            "unavailable_cast": unavailable_cast,
        }

    # ------------------------------------------------------------------
    # Location is available, but cast is not fully verified.
    # ------------------------------------------------------------------

    if unknown_cast or unavailable_cast:

        reason_parts: list[str] = []

        if unknown_cast:
            reason_parts.append(
                "Replacement cast availability unknown: "
                + ", ".join(unknown_cast)
                + "."
            )

        if unavailable_cast:
            reason_parts.append(
                "Unavailable replacement cast: "
                + ", ".join(unavailable_cast)
                + "."
            )

        return {
            "feasible": False,
            "reason": " ".join(reason_parts),
            "affected_scene": affected_id,
            "replacement_scene": replacement_id,
            "date": date_value,
            "replacement_title": replacement.get(
                "title"
            ),
            "replacement_characters": (
                replacement_characters
            ),
            "replacement_location": location_name,
            "maya_required": False,
            "location": location_result,
            "cast": cast_results,
            "unknown_cast": unknown_cast,
            "unavailable_cast": unavailable_cast,
        }

    # ------------------------------------------------------------------
    # Fully verified replacement.
    # ------------------------------------------------------------------

    return {
        "feasible": True,
        "reason": (
            f"Scene {replacement_id} is a verified "
            f"replacement for Scene {affected_id} "
            f"on {date_value}: Maya Chen is not "
            f"required, {location_name} is available, "
            f"and all required cast members are "
            f"available."
        ),
        "affected_scene": affected_id,
        "replacement_scene": replacement_id,
        "date": date_value,
        "replacement_title": replacement.get(
            "title"
        ),
        "replacement_characters": (
            replacement_characters
        ),
        "replacement_location": location_name,
        "maya_required": False,
        "location": location_result,
        "cast": cast_results,
        "unknown_cast": unknown_cast,
        "unavailable_cast": unavailable_cast,
    }


# ============================================================================
# SCHEDULE IMPACT
# ============================================================================


def estimate_schedule_impact(
    plan: str,
    affected_scene: str = "42",
) -> dict:
    """
    Return deterministic schedule estimates.

    Valid plans:

        reschedule
        swap
        rewrite

    These are scenario estimates, not executed production actions.
    """

    normalized_plan = str(plan).strip().lower()

    normalized_scene = _normalize_scene_id(
        affected_scene
    )

    estimates = {
        "reschedule": {
            "delay_days": 1,
            "crew_hours": 10,
        },
        "swap": {
            "delay_days": 0,
            "crew_hours": 1,
        },
        "rewrite": {
            "delay_days": 0,
            "crew_hours": 4,
        },
    }

    estimate = estimates.get(
        normalized_plan
    )

    if estimate is None:
        return {
            "plan": normalized_plan,
            "affected_scene": normalized_scene,
            "error": (
                "Unknown plan. Expected one of: "
                "reschedule, swap, rewrite"
            ),
        }

    return {
        "plan": normalized_plan,
        "affected_scene": normalized_scene,
        **estimate,
    }


# ============================================================================
# BUDGET IMPACT
# ============================================================================


def estimate_budget_impact(
    plan: str,
    affected_scene: str = "42",
) -> dict:
    """
    Return deterministic budget estimates.

    Valid plans:

        reschedule
        swap
        rewrite

    These are estimates, not actual invoices or spending.
    """

    normalized_plan = str(plan).strip().lower()

    normalized_scene = _normalize_scene_id(
        affected_scene
    )

    estimates = {
        "reschedule": {
            "incremental_usd": 18420,
            "creative_risk": "low",
        },
        "swap": {
            "incremental_usd": 2350,
            "creative_risk": "medium",
        },
        "rewrite": {
            "incremental_usd": 900,
            "creative_risk": "high",
        },
    }

    estimate = estimates.get(
        normalized_plan
    )

    if estimate is None:
        return {
            "plan": normalized_plan,
            "affected_scene": normalized_scene,
            "error": (
                "Unknown plan. Expected one of: "
                "reschedule, swap, rewrite"
            ),
        }

    return {
        "plan": normalized_plan,
        "affected_scene": normalized_scene,
        **estimate,
    }