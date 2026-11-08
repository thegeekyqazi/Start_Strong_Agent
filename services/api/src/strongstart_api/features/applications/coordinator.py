"""Coordinator acceptance of role results (SEC-12; engineering s8.1, s13.2; C2 spec s4).

Adapters return raw text only. The coordinator wraps each result in a server-built
envelope and accepts it only when the task ID and role match the task it issued. The
per-role validators then enforce the strict schema, evidence permissions (fact IDs within
the identity-scoped bundle) and the absence of approval/permission/fact-overwrite fields.
A role result never changes facts, permissions or workflow state.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .models.base import ModelAdapter, ModelOutputRejected, ModelTimeout, StructuredTask

ROLE_FOR_OPERATION = {
    "draft_answer": "writer",
    "plan_application": "planner",
    "numerical_review": "numerical_reviewer",
    "meaning_review": "meaning_reviewer",
}


@dataclass(frozen=True)
class RoleResult:
    task_id: str
    role: str
    raw: str


def accept(issued: StructuredTask, result: RoleResult) -> str:
    if result.task_id != issued.task_id:
        raise ModelOutputRejected(issues=["sec12_task_mismatch"])
    if result.role != ROLE_FOR_OPERATION.get(issued.operation):
        raise ModelOutputRejected(issues=["sec12_role_mismatch"])
    return result.raw


async def run_role(adapter: ModelAdapter, task: StructuredTask, timeout_seconds: float) -> str:
    try:
        raw = await asyncio.wait_for(adapter.complete(task), timeout=timeout_seconds)
    except TimeoutError:
        raise ModelTimeout() from None
    return accept(task, RoleResult(task.task_id, ROLE_FOR_OPERATION[task.operation], raw))
