from app.models.action import Action
from app.models.action_repository import update_action

ALLOWED_TRANSITIONS = {
    "pending": {"approved", "rejected", "cancelled"},
    "approved": {"executing", "cancelled"},
    "executing": {"completed", "failed", "cancelled"},
    "completed": set(),
    "rejected": set(),
    "failed": set(),
    "cancelled": set(),
}


def transition_action(action: Action, status: str, result: dict | None = None) -> Action:
    allowed = ALLOWED_TRANSITIONS.get(action.status, set())
    if status not in allowed:
        raise ValueError(
            f"Invalid action transition: {action.status} -> {status}"
        )

    return update_action(action.id, status=status, result=result)


def approve_action(action: Action) -> Action:
    return transition_action(action, "approved")


def reject_action(action: Action) -> Action:
    return transition_action(action, "rejected")


def begin_action(action: Action) -> Action:
    return transition_action(action, "executing")


def complete_action(action: Action, result: dict) -> Action:
    return transition_action(action, "completed", result=result)


def fail_action(action: Action, result: dict | None = None) -> Action:
    return transition_action(action, "failed", result=result)


def cancel_action(action: Action) -> Action:
    return transition_action(action, "cancelled")
