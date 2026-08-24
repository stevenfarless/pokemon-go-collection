"""Validate the task-based human usability benchmark contract for issue #155."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_PERSONAS = {"beginner", "intermediate", "advanced", "assistive"}
ALLOWED_RISKS = {"normal", "destructive", "scarce-resource"}
HIGH_RISK = {"destructive", "scarce-resource"}


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    required_personas = payload.get("required_personas")
    required_workflows = payload.get("required_workflows")
    tasks = payload.get("tasks")
    if not isinstance(required_personas, list) or not required_personas:
        errors.append("required_personas must be a non-empty list")
        required_personas = []
    if not isinstance(required_workflows, list) or not required_workflows:
        errors.append("required_workflows must be a non-empty list")
        required_workflows = []
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty list")
        tasks = []

    if len(required_workflows) != len(set(required_workflows)):
        errors.append("required_workflows must not contain duplicates")
    unknown_personas = set(required_personas) - ALLOWED_PERSONAS
    if unknown_personas:
        errors.append(f"unsupported required personas: {sorted(unknown_personas)}")

    ids: set[str] = set()
    workflow_counts: Counter[str] = Counter()
    persona_counts: Counter[str] = Counter()

    for index, task in enumerate(tasks):
        prefix = f"tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} must be an object")
            continue
        task_id = task.get("id")
        persona = task.get("persona")
        workflow = task.get("workflow")
        prompt = task.get("prompt")
        criteria = task.get("success_criteria")
        risk = task.get("risk")

        if not isinstance(task_id, str) or not task_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif task_id in ids:
            errors.append(f"duplicate task id: {task_id}")
        else:
            ids.add(task_id)

        if persona not in ALLOWED_PERSONAS:
            errors.append(f"{prefix}.persona must be one of {sorted(ALLOWED_PERSONAS)}")
        else:
            persona_counts[persona] += 1

        if not isinstance(workflow, str) or not workflow.strip():
            errors.append(f"{prefix}.workflow must be a non-empty string")
        else:
            workflow_counts[workflow] += 1

        if not isinstance(prompt, str) or len(prompt.strip()) < 20:
            errors.append(f"{prefix}.prompt must be a specific task prompt")
        if not isinstance(criteria, list) or not criteria or not all(isinstance(item, str) and item.strip() for item in criteria):
            errors.append(f"{prefix}.success_criteria must be a non-empty list of strings")
        if risk not in ALLOWED_RISKS:
            errors.append(f"{prefix}.risk must be one of {sorted(ALLOWED_RISKS)}")
        if risk in HIGH_RISK and not str(task.get("critical_error_definition") or "").strip():
            errors.append(f"{prefix} high-risk task requires critical_error_definition")
        modes = task.get("accessibility_modes")
        if modes is not None and (not isinstance(modes, list) or not all(isinstance(item, str) and item.strip() for item in modes)):
            errors.append(f"{prefix}.accessibility_modes must be a list of strings when present")

    for persona in required_personas:
        if persona_counts[persona] == 0:
            errors.append(f"required persona has no tasks: {persona}")
    for workflow in required_workflows:
        if workflow_counts[workflow] == 0:
            errors.append(f"required workflow has no task-based criterion: {workflow}")

    undeclared_workflows = sorted(set(workflow_counts) - set(required_workflows))
    if undeclared_workflows:
        errors.append(f"tasks reference undeclared workflows: {undeclared_workflows}")

    assistive_tasks = [task for task in tasks if isinstance(task, dict) and task.get("persona") == "assistive"]
    if not assistive_tasks:
        errors.append("at least one assistive-technology task is required")
    elif not all(task.get("accessibility_modes") for task in assistive_tasks):
        errors.append("every assistive task must name at least one accessibility mode")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="config/usability-tasks.json")
    args = parser.parse_args()
    path = Path(args.path)
    try:
        payload = load_payload(path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"usability benchmark contract could not be read: {exc}")
        return 1
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"Usability benchmark contract OK: {len(payload['tasks'])} tasks, "
        f"{len(payload['required_workflows'])} workflows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
