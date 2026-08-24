import copy
import json
from pathlib import Path

from scripts.check_usability_tasks import validate


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = json.loads((ROOT / "config" / "usability-tasks.json").read_text(encoding="utf-8"))


def test_usability_task_contract_is_complete():
    assert validate(PAYLOAD) == []


def test_missing_workflow_coverage_fails_closed():
    payload = copy.deepcopy(PAYLOAD)
    workflow = payload["required_workflows"][0]
    payload["tasks"] = [task for task in payload["tasks"] if task["workflow"] != workflow]
    assert any(workflow in error for error in validate(payload))


def test_high_risk_tasks_require_critical_error_definition():
    payload = copy.deepcopy(PAYLOAD)
    task = next(task for task in payload["tasks"] if task["risk"] == "destructive")
    task.pop("critical_error_definition")
    assert any("critical_error_definition" in error for error in validate(payload))


def test_assistive_tasks_name_accessibility_mode():
    payload = copy.deepcopy(PAYLOAD)
    task = next(task for task in payload["tasks"] if task["persona"] == "assistive")
    task["accessibility_modes"] = []
    assert any("assistive" in error.lower() or "accessibility_modes" in error for error in validate(payload))
