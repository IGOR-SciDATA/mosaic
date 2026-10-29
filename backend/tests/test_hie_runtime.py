import pytest

from app.services.hie_runtime import HIEExecutionBudget, HIERuntimeCancelled, HIERuntimeLimitExceeded


def test_provider_budget_blocks_excess_call_before_reserving_it():
    budget = HIEExecutionBudget(max_provider_calls=1)
    config = budget.before_provider_call([{"role": "user", "content": "hello"}], {})
    assert config["request_timeout_seconds"] > 0
    assert config["num_predict"] == 1500
    assert config["max_output_tokens"] == 1500
    assert budget.provider_calls == 1

    with pytest.raises(HIERuntimeLimitExceeded, match="provider-call budget"):
        budget.before_provider_call([{"role": "user", "content": "second"}], {})
    assert budget.provider_calls == 1


def test_input_budget_blocks_provider_call_before_counter_increments():
    budget = HIEExecutionBudget(max_input_chars_per_call=3)
    with pytest.raises(HIERuntimeLimitExceeded, match="input"):
        budget.before_provider_call([{"role": "user", "content": "four"}], {})
    assert budget.provider_calls == 0


def test_output_and_tool_budgets_are_enforced():
    budget = HIEExecutionBudget(max_output_chars_per_call=3, max_tool_calls=1)
    with pytest.raises(HIERuntimeLimitExceeded, match="output"):
        budget.after_provider_call("four")
    budget.before_tool_call()
    with pytest.raises(HIERuntimeLimitExceeded, match="tool-call budget"):
        budget.before_tool_call()
    assert budget.tool_calls == 1


def test_retry_budget_and_cancellation_are_checked_at_boundary():
    budget = HIEExecutionBudget(max_retries=1)
    budget.before_retry()
    with pytest.raises(HIERuntimeLimitExceeded, match="retry budget"):
        budget.before_retry()

    cancelled = HIEExecutionBudget(cancelled=lambda: True)
    with pytest.raises(HIERuntimeCancelled):
        cancelled.before_tool_call()
    assert cancelled.tool_calls == 0


def test_invalid_runtime_budgets_fail_closed():
    with pytest.raises(ValueError, match="positive integer"):
        HIEExecutionBudget(max_provider_calls=True)
    with pytest.raises(ValueError, match="positive number"):
        HIEExecutionBudget(wall_seconds=0)
