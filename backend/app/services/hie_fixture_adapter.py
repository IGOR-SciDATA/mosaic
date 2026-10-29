"""Test-only bridge between HIE orchestration and disposable data fixtures.

This adapter does not execute files from the fixture and does not provide a
production workspace integration. Callbacks must be deterministic, local test
functions; they must not access network services, mutate canonical project
files, or execute fixture contents as code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.services.hie_orchestrator import run_candidate_experiment
from app.services.hie_workspace import create_disposable_workspace

RunnerFactory = Callable[[Path], Callable[[], dict[str, Any]]]
ProbeRunnerFactory = Callable[[Path], Callable[[dict[str, Any]], dict[str, Any]]]


def run_disposable_fixture_experiment(
    source: str | Path,
    *,
    baseline_runner_factory: RunnerFactory,
    probe_runner_factory: ProbeRunnerFactory,
    **experiment_kwargs: Any,
) -> dict[str, Any]:
    """Run one comparison against two independent disposable fixture copies.

    The baseline and candidate each receive a distinct temporary workspace,
    both copied from the same read-only source fixture. The workspaces are
    removed on success or failure. This is a test adapter, not a security
    sandbox: supplied callbacks remain trusted code and must be side-effect-free.
    """
    if "isolated_fixture" in experiment_kwargs:
        raise ValueError("Fixture isolation is controlled by this adapter")

    with create_disposable_workspace(source) as baseline_workspace:
        with create_disposable_workspace(source) as candidate_workspace:
            if baseline_workspace.root == candidate_workspace.root:
                raise RuntimeError("Baseline and candidate fixtures must be independent")

            baseline_runner = baseline_runner_factory(baseline_workspace.root)
            probe_runner = probe_runner_factory(candidate_workspace.root)
            if not callable(baseline_runner) or not callable(probe_runner):
                raise TypeError("Runner factories must return callable runners")

            return run_candidate_experiment(
                **experiment_kwargs,
                baseline_runner=baseline_runner,
                probe_runner=probe_runner,
                isolated_fixture=True,
            )
