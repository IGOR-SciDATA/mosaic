"""Sequential coordination using the existing Task Engine and persisted Task.plan JSON."""

import hashlib
from typing import Any, Callable

from app.models.task_event_repository import create_task_event
from app.models.task_repository import create_task, get_task, list_tasks, update_task
from app.services.agent import run_agent
from app.services.agent_decision import create_provider_decider
from app.services.agent_profiles import PROFILE_NAMES, create_agent_profile_snapshot

MAX_SUBTASKS = 10
MAX_DEPENDENCY_OUTPUT_CHARS = 2_000
MAX_INTEGRATED_OUTPUT_CHARS = 20_000
ACCEPTANCE_TYPES = {"non_empty", "contains", "not_contains", "min_chars"}


def validate_coordinator_plan(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(plan, dict):
        raise ValueError("Coordinator plan must be an object")
    raw = plan.get("subtasks")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SUBTASKS:
        raise ValueError(f"Coordinator plan must contain 1 to {MAX_SUBTASKS} subtasks")

    specs: list[dict[str, Any]] = []
    keys: set[str] = set()
    for index, raw_spec in enumerate(raw):
        if not isinstance(raw_spec, dict):
            raise ValueError(f"Subtask {index} must be an object")
        key = raw_spec.get("id")
        goal = raw_spec.get("goal")
        profile = raw_spec.get("profile")
        if not isinstance(key, str) or not key.strip() or len(key) > 64:
            raise ValueError(f"Subtask {index} requires a short non-empty id")
        if key in keys:
            raise ValueError(f"Duplicate subtask id: {key}")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 2_000:
            raise ValueError(f"Subtask {key} requires a goal of at most 2000 characters")
        if profile not in PROFILE_NAMES:
            raise ValueError(f"Subtask {key} uses an unknown agent profile")
        dependencies = raw_spec.get("depends_on", [])
        if (
            not isinstance(dependencies, list)
            or any(not isinstance(dep, str) for dep in dependencies)
            or len(set(dependencies)) != len(dependencies)
            or key in dependencies
        ):
            raise ValueError(f"Subtask {key} has invalid dependencies")
        inputs = raw_spec.get("inputs", [])
        if not isinstance(inputs, list) or any(not isinstance(item, str) for item in inputs):
            raise ValueError(f"Subtask {key} inputs must be a list of strings")
        if len(inputs) > 20 or any(len(item) > 2_000 for item in inputs):
            raise ValueError(f"Subtask {key} inputs exceed the supported bounds")
        criteria = raw_spec.get("acceptance_criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError(f"Subtask {key} requires acceptance_criteria")
        if len(criteria) > 20:
            raise ValueError(f"Subtask {key} has too many acceptance criteria")
        normalized_criteria = []
        for criterion in criteria:
            if not isinstance(criterion, dict) or criterion.get("type") not in ACCEPTANCE_TYPES:
                raise ValueError(f"Subtask {key} has an unsupported acceptance criterion")
            kind = criterion["type"]
            value = criterion.get("value")
            if kind in {"contains", "not_contains"} and (not isinstance(value, str) or not value):
                raise ValueError(f"Subtask {key} criterion {kind} requires a non-empty value")
            if kind == "min_chars" and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise ValueError(f"Subtask {key} criterion min_chars requires a positive integer")
            normalized_criteria.append({"type": kind, **({"value": value} if value is not None else {})})
        keys.add(key)
        specs.append({
            "id": key,
            "goal": goal.strip(),
            "profile": profile,
            "depends_on": dependencies,
            "inputs": inputs,
            "acceptance_criteria": normalized_criteria,
        })

    known = {spec["id"] for spec in specs}
    for spec in specs:
        unknown = set(spec["depends_on"]) - known
        if unknown:
            raise ValueError(f"Subtask {spec['id']} depends on unknown ids: {', '.join(sorted(unknown))}")

    pending = list(specs)
    ordered: list[dict[str, Any]] = []
    completed_keys: set[str] = set()
    while pending:
        ready_index = next(
            (i for i, spec in enumerate(pending) if set(spec["depends_on"]) <= completed_keys),
            None,
        )
        if ready_index is None:
            raise ValueError("Coordinator dependencies contain a cycle")
        spec = pending.pop(ready_index)
        ordered.append(spec)
        completed_keys.add(spec["id"])
    return ordered


def _record_coordinator_event(
    task: Any,
    event_name: str,
    message: str,
    status: str,
    metadata: dict[str, Any],
    *,
    level: str = "info",
) -> None:
    try:
        create_task_event(
            task_id=task.id,
            conversation_id=task.conversation_id,
            project_id=task.project_id,
            component="coordinator",
            event_name=event_name,
            message=message,
            status=status,
            level=level,
            metadata=metadata,
        )
    except Exception:
        return


def _criteria_failures(spec: dict[str, Any], output: str) -> list[str]:
    failures = []
    for criterion in spec["acceptance_criteria"]:
        kind = criterion["type"]
        value = criterion.get("value")
        if kind == "non_empty" and not output.strip():
            failures.append("output must not be empty")
        elif kind == "contains" and value not in output:
            failures.append(f"output does not contain required text: {value}")
        elif kind == "not_contains" and value in output:
            failures.append(f"output contains forbidden text: {value}")
        elif kind == "min_chars" and len(output.strip()) < value:
            failures.append(f"output is shorter than {value} characters")
    return failures


def _fail_parent(parent: Any, *, reason: str, child_id: int | None = None) -> Any:
    plan = dict(parent.plan or {})
    coordinator = dict(plan.get("coordinator") or {})
    coordinator["status"] = "failed"
    if child_id is not None:
        coordinator["failed_child_task_id"] = child_id
    plan["coordinator"] = coordinator
    result = {
        "error": reason[:1_000],
        "coordinator": {
            "status": "failed",
            "failed_child_task_id": child_id,
        },
    }
    try:
        parent = update_task(parent.id, status="failed", plan=plan, result=result)
    except ValueError:
        parent = get_task(parent.id) or parent
    _record_coordinator_event(
        parent,
        "coordinator.failed",
        "Sequential coordination stopped before all subtasks completed.",
        "failed",
        {"failed_child_task_id": child_id, "error_type": "SubtaskExecutionOrValidationError"},
        level="error",
    )
    return parent


def run_coordinated_task(
    task_id: int,
    decider_factory: Callable[[Any], Callable[[list[dict[str, str]]], dict[str, Any]]] | None = None,
) -> Any:
    """Run dependent child Tasks sequentially; all execution remains in the existing Task Engine."""
    parent = get_task(task_id)
    if parent is None:
        raise ValueError("Coordinator Task not found")
    if parent.conversation_id is None:
        raise ValueError("Coordinator Task requires a conversation with an explicitly selected model")
    if parent.status not in {"pending", "planning", "executing", "awaiting_approval"}:
        raise ValueError(f"Coordinator Task cannot run from state {parent.status}")

    plan = dict(parent.plan or {})
    ordered_specs = validate_coordinator_plan(plan)
    if parent.status == "pending":
        parent = update_task(parent.id, status="planning")

    existing = list_tasks(conversation_id=parent.conversation_id)
    existing_by_key = {}
    for candidate in existing:
        candidate_plan = candidate.plan if isinstance(candidate.plan, dict) else {}
        if candidate_plan.get("coordinator_task_id") == parent.id:
            subtask_key = candidate_plan.get("subtask_key")
            if isinstance(subtask_key, str):
                existing_by_key[subtask_key] = candidate

    children: dict[str, Any] = {}
    for spec in ordered_specs:
        child = existing_by_key.get(spec["id"])
        if child is None:
            child_plan = {
                "goal": spec["goal"],
                "agent_profile_snapshot": create_agent_profile_snapshot(spec["profile"]),
                "coordinator_task_id": parent.id,
                "subtask_key": spec["id"],
                "depends_on_keys": list(spec["depends_on"]),
                "acceptance_criteria": spec["acceptance_criteria"],
                "inputs": list(spec["inputs"]),
                "dependency_results": {},
            }
            child = create_task(
                type=parent.type,
                mode="agent",
                conversation_id=parent.conversation_id,
                project_id=parent.project_id,
                plan=child_plan,
            )
        children[spec["id"]] = child

    plan = dict(parent.plan or {})
    coordinator = dict(plan.get("coordinator") or {})
    coordinator.setdefault("status", "executing")
    coordinator["children"] = {key: child.id for key, child in children.items()}
    coordinator["order"] = [spec["id"] for spec in ordered_specs]
    coordinator.setdefault("results", {})
    plan["coordinator"] = coordinator
    parent = update_task(parent.id, plan=plan)
    if parent.status in {"planning", "awaiting_approval"}:
        parent = update_task(parent.id, status="executing")
    _record_coordinator_event(
        parent,
        "coordinator.started" if not coordinator.get("started") else "coordinator.resumed",
        "Sequential coordination started or resumed.",
        "executing",
        {"subtask_count": len(ordered_specs), "order": coordinator["order"]},
    )
    coordinator["started"] = True

    outputs: dict[str, str] = {}
    for spec in ordered_specs:
        key = spec["id"]
        child = get_task(children[key].id)
        if child is None:
            return _fail_parent(parent, reason=f"Subtask {key} disappeared", child_id=children[key].id)

        dependency_results: dict[str, Any] = {}
        for dependency in spec["depends_on"]:
            dependency_task = get_task(children[dependency].id)
            if dependency_task is None or dependency_task.status != "completed":
                return _fail_parent(
                    parent,
                    reason=f"Dependency {dependency} for subtask {key} is not completed",
                    child_id=child.id,
                )
            dependency_result = dependency_task.result if isinstance(dependency_task.result, dict) else {}
            dependency_output = str(dependency_result.get("output", ""))[:MAX_DEPENDENCY_OUTPUT_CHARS]
            dependency_results[dependency] = {
                "task_id": dependency_task.id,
                "status": dependency_task.status,
                "output": dependency_output,
                "sha256": hashlib.sha256(dependency_output.encode("utf-8")).hexdigest(),
            }

        child_plan = dict(child.plan or {})
        child_plan["dependency_results"] = dependency_results
        child_plan["depends_on_task_ids"] = [children[dependency].id for dependency in spec["depends_on"]]
        child_plan["inputs"] = list(spec["inputs"])
        child_plan["acceptance_criteria"] = spec["acceptance_criteria"]
        child = update_task(child.id, plan=child_plan)

        if child.status == "awaiting_approval":
            plan = dict(parent.plan or {})
            coordinator = dict(plan.get("coordinator") or {})
            coordinator.update({"status": "awaiting_approval", "active_child_task_id": child.id})
            plan["coordinator"] = coordinator
            parent = update_task(parent.id, status="awaiting_approval", plan=plan, result={
                "coordinator_status": "awaiting_approval",
                "active_child_task_id": child.id,
            })
            _record_coordinator_event(
                parent, "coordinator.awaiting_approval",
                "A child Task is waiting for user approval.", "awaiting_approval",
                {"child_task_id": child.id, "subtask_key": key},
            )
            return parent

        if child.status in {"failed", "cancelled"}:
            return _fail_parent(parent, reason=f"Subtask {key} ended with status {child.status}", child_id=child.id)

        if child.status != "completed":
            _record_coordinator_event(
                parent, "coordinator.subtask_started",
                "Sequential child Task started.", "executing",
                {"child_task_id": child.id, "subtask_key": key, "profile": spec["profile"]},
            )
            decider = decider_factory(child) if decider_factory else create_provider_decider(child.id)
            try:
                child_result = run_agent(child.id, decider)
            except Exception as exc:
                child = get_task(child.id) or child
                if child.status in {"pending", "planning", "executing", "awaiting_approval", "validating"}:
                    try:
                        child = update_task(child.id, status="failed", result={"error_type": type(exc).__name__})
                    except ValueError:
                        child = get_task(child.id) or child
                return _fail_parent(parent, reason=f"Subtask {key} raised {type(exc).__name__}", child_id=child.id)
            child = get_task(child.id) or child
            if child_result.get("status") == "awaiting_approval" or child.status == "awaiting_approval":
                plan = dict(parent.plan or {})
                coordinator = dict(plan.get("coordinator") or {})
                coordinator.update({"status": "awaiting_approval", "active_child_task_id": child.id})
                plan["coordinator"] = coordinator
                parent = update_task(parent.id, status="awaiting_approval", plan=plan, result={
                    "coordinator_status": "awaiting_approval",
                    "active_child_task_id": child.id,
                })
                _record_coordinator_event(
                    parent, "coordinator.awaiting_approval",
                    "A child Task is waiting for user approval.", "awaiting_approval",
                    {"child_task_id": child.id, "subtask_key": key},
                )
                return parent
            if child.status != "completed":
                return _fail_parent(parent, reason=f"Subtask {key} ended with status {child.status}", child_id=child.id)

        child_result = child.result if isinstance(child.result, dict) else {}
        output = str(child_result.get("output", ""))
        failures = _criteria_failures(spec, output)
        if failures:
            _record_coordinator_event(
                parent, "coordinator.subtask_validation_failed",
                "Subtask output failed deterministic acceptance criteria.", "failed",
                {"child_task_id": child.id, "subtask_key": key, "failed_criteria": failures},
                level="error",
            )
            return _fail_parent(parent, reason=f"Subtask {key} failed acceptance criteria", child_id=child.id)

        outputs[key] = output
        plan = dict(parent.plan or {})
        coordinator = dict(plan.get("coordinator") or {})
        results = dict(coordinator.get("results") or {})
        results[key] = {
            "task_id": child.id,
            "profile": spec["profile"],
            "status": "completed",
            "output_chars": len(output),
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        }
        coordinator["results"] = results
        coordinator["status"] = "executing"
        coordinator.pop("active_child_task_id", None)
        plan["coordinator"] = coordinator
        parent = update_task(parent.id, plan=plan)
        _record_coordinator_event(
            parent, "coordinator.subtask_completed",
            "Subtask completed and passed deterministic acceptance criteria.", "completed",
            {
                "child_task_id": child.id,
                "subtask_key": key,
                "profile": spec["profile"],
                "depends_on": spec["depends_on"],
                "output_chars": len(output),
                "output_sha256": results[key]["output_sha256"],
            },
        )

    sections = [
        f"## {spec['id']} — {spec['profile']}\n{outputs.get(spec['id'], '')}"
        for spec in ordered_specs
    ]
    integrated_output = "\n\n".join(sections)[:MAX_INTEGRATED_OUTPUT_CHARS]
    summaries = [
        {
            "key": spec["id"],
            "task_id": children[spec["id"]].id,
            "profile": spec["profile"],
            "status": "completed",
            "output_sha256": hashlib.sha256(outputs.get(spec["id"], "").encode("utf-8")).hexdigest(),
        }
        for spec in ordered_specs
    ]
    plan = dict(parent.plan or {})
    coordinator = dict(plan.get("coordinator") or {})
    coordinator["status"] = "completed"
    coordinator.pop("active_child_task_id", None)
    plan["coordinator"] = coordinator
    parent = update_task(
        parent.id,
        status="completed",
        plan=plan,
        result={
            "output": integrated_output,
            "coordinator": {"status": "completed", "subtasks": summaries},
        },
    )
    _record_coordinator_event(
        parent, "coordinator.completed",
        "All sequential subtasks completed and their outputs were integrated.", "completed",
        {"subtask_count": len(ordered_specs), "integrated_output_chars": len(integrated_output)},
    )
    return parent
