"""
Routing module — the single source of truth for route strings and routing logic.

Responsibilities:
  - Define all valid route destinations as class constants (Routes).
  - Define route urgency ranking (ROUTE_RANK) used by the rules engine
    to break ties when multiple rules fire at the same priority.
  - resolve_route(): apply unit-type and patient-context overrides on top
    of the rules engine's suggested route.

Rules engine imports Routes and ROUTE_RANK.
Decision layer calls resolve_route().
Nothing else should construct route strings directly.
"""

from __future__ import annotations

from models import AlertIn, AlertType, Priority


# ---------------------------------------------------------------------------
# Route constants
# ---------------------------------------------------------------------------

class Routes:
    """All valid response-team destinations. Use these constants everywhere."""
    RAPID_RESPONSE    = "Rapid Response Team"
    ICU_TEAM          = "ICU Team (Intensivist + Nurse)"
    CHARGE_NURSE      = "Charge Nurse"
    BEDSIDE_IMMEDIATE = "Bedside Nurse (immediate)"
    BEDSIDE_5MIN      = "Bedside Nurse (5 min)"
    BEDSIDE_ROUTINE   = "Bedside Nurse"
    PHARMACY_CONSULT  = "Pharmacy + Bedside Nurse"


# Urgency rank for routes — used as a tiebreaker when two rules fire at the
# same priority level.  Higher rank = more urgent / preferred route.
ROUTE_RANK: dict[str, int] = {
    Routes.RAPID_RESPONSE:    6,
    Routes.ICU_TEAM:          6,
    Routes.CHARGE_NURSE:      4,
    Routes.PHARMACY_CONSULT:  4,
    Routes.BEDSIDE_IMMEDIATE: 3,
    Routes.BEDSIDE_5MIN:      2,
    Routes.BEDSIDE_ROUTINE:   1,
}


# ---------------------------------------------------------------------------
# Unit classification helpers
# ---------------------------------------------------------------------------

_ICU_KEYWORDS      = frozenset({"icu", "intensive care", "critical care",
                                 "step-down", "stepdown", "ccu", "micu", "sicu", "nicu"})
_PHARMACY_DRUGS    = frozenset({"insulin", "heparin", "tpa", "alteplase",
                                 "chemotherapy", "chemo", "warfarin", "vancomycin"})


def _unit_is_icu(unit: str) -> bool:
    lower = unit.lower()
    return any(k in lower for k in _ICU_KEYWORDS)


# ---------------------------------------------------------------------------
# Route resolution
# ---------------------------------------------------------------------------

def resolve_route(
    alert: AlertIn,
    baseline_priority: Priority,
    rule_suggested_route: str,
) -> str:
    """
    Refine the rules engine's suggested route using unit type and patient context.

    Precedence (highest → lowest):
      1. Critical in ICU            → ICU Team
      2. Critical elsewhere         → Rapid Response Team
      3. High in ICU                → ICU Team
      4. Infusion pump + high-risk drug → Pharmacy consult
      5. Rules engine suggestion    (fallback)

    The priority floor is NOT enforced here — that is the decision layer's job.
    """
    # 1 & 2: Critical always escalates, unit determines which team
    if baseline_priority == Priority.critical:
        return Routes.ICU_TEAM if _unit_is_icu(alert.unit) else Routes.RAPID_RESPONSE

    # 3: High in ICU requires intensivist involvement
    if baseline_priority == Priority.high and _unit_is_icu(alert.unit):
        return Routes.ICU_TEAM

    # 4: Infusion alarm with a high-risk drug — loop pharmacy in
    if alert.alert_type == AlertType.infusion_pump:
        infusate = str(alert.additional_context.get("infusate", "")).lower()
        if any(drug in infusate for drug in _PHARMACY_DRUGS):
            return Routes.PHARMACY_CONSULT

    # 5: Fall back to whatever the rules engine suggested
    return rule_suggested_route
