"""
Shared test fixtures and helpers.

make_alert() is the primary entry point — build an AlertIn with sensible
defaults, then override only the fields relevant to the test case.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from backend/ without installing as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import AlertIn, AlertType, VitalSigns, RecentContext


FIXED_TS = datetime(2024, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def make_alert(
    alert_type: AlertType = AlertType.tachycardia,
    vital_signs: VitalSigns | None = None,
    repeat_count: int = 0,
    unit: str = "3-North Telemetry",
    recent_context: RecentContext | None = None,
    additional_context: dict | None = None,
    alert_id: str = "TEST-001",
) -> AlertIn:
    return AlertIn(
        alert_id=alert_id,
        source_system="test_harness",
        alert_type=alert_type,
        patient_id="PT-TEST",
        unit=unit,
        room="301",
        bed="A",
        timestamp=FIXED_TS,
        vital_signs=vital_signs or VitalSigns(),
        repeat_count=repeat_count,
        recent_context=recent_context or RecentContext(),
        additional_context=additional_context or {},
    )
