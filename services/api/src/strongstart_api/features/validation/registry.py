"""Closed A3 source-rule registry; requests cannot supply executable code."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from strongstart_contracts import RuleCapability, ValidationResult

from .rules import (
    RULE_VERSION,
    SourceContext,
    src01,
    src02,
    src03,
    src04,
    src05,
    src06,
    src07,
    src08,
    src09,
    src10,
)

Rule = Callable[[SourceContext], ValidationResult]


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    priority: Literal["P0", "P1"]
    evaluator: Rule

    def capability(self) -> RuleCapability:
        return RuleCapability(
            rule_id=self.rule_id,
            rule_version=RULE_VERSION,
            priority=self.priority,
            state="implemented",
        )


DEFINITIONS = (
    RuleDefinition("SRC-01", "P0", src01),
    RuleDefinition("SRC-02", "P0", src02),
    RuleDefinition("SRC-03", "P0", src03),
    RuleDefinition("SRC-04", "P0", src04),
    RuleDefinition("SRC-05", "P0", src05),
    RuleDefinition("SRC-06", "P1", src06),
    RuleDefinition("SRC-07", "P1", src07),
    RuleDefinition("SRC-08", "P1", src08),
    RuleDefinition("SRC-09", "P1", src09),
    RuleDefinition("SRC-10", "P1", src10),
)
REGISTRY = {definition.rule_id: definition for definition in DEFINITIONS}


def capabilities() -> list[RuleCapability]:
    return [definition.capability() for definition in DEFINITIONS]


def run(ctx: SourceContext, requested: list[str]) -> list[ValidationResult]:
    selected = requested or list(REGISTRY)
    return [REGISTRY[rule_id].evaluator(ctx) for rule_id in sorted(selected)]
