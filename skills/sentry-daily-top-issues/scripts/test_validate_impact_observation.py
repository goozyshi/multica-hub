"""Regression checks for the structured impact-observation callback snapshot."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_feishu_card.py")
SPEC = importlib.util.spec_from_file_location("validate_feishu_card", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def snapshot() -> dict:
    return {
        "schema": "sentry_impact_table_v1",
        "time_window": "24h",
        "filter": "is:unresolved level:error",
        "window_start": "2026-09-02T00:00:00Z",
        "window_end": "2026-09-02T23:59:59Z",
        "columns": list(module.OBSERVATION_TABLE_COLUMNS),
        "rows": [
            {
                "group": "web",
                "project": "omigo-h5",
                "issue_id": "OMIGO-H5-B",
                "issue_title": "platform not supported",
                "event_count": 2,
                "user_count": 2,
                "first_seen": "2026-09-02T01:00:00Z",
                "last_seen": "2026-09-02T02:00:00Z",
                "release": "1.8.3",
                "environment": "prod",
            }
        ],
    }


def callback_value() -> dict:
    value = {
        "project": "omigo-h5",
        "issue_id": "OMIGO-H5-B",
        "time_window": "24h",
        "filter": "is:unresolved level:error",
        "window_start": "2026-09-02T00:00:00Z",
        "window_end": "2026-09-02T23:59:59Z",
        "impact_observation_snapshot": snapshot(),
    }
    return value


def validate(value: dict) -> list[dict]:
    validator = module.CardValidation()
    module.validate_observation_snapshot(
        value,
        validator,
        "$.value",
    )
    return validator.errors


valid_errors = validate(callback_value())
assert not valid_errors, valid_errors

missing_snapshot = callback_value()
del missing_snapshot["impact_observation_snapshot"]
errors = validate(missing_snapshot)
assert any(error["code"] == "missing_observation_snapshot" for error in errors), errors

wrong_issue = callback_value()
wrong_issue["impact_observation_snapshot"]["rows"][0]["issue_id"] = "OTHER"
errors = validate(wrong_issue)
assert any(error["code"] == "observation_row_mismatch" for error in errors), errors

print("structured impact observation checks passed")
