"""Finite rule tests and base-policy composition (C4-SKL-001 s6.1, s9; C4-11/C4-17).

Practices compile into C's existing finite WritingPolicy records, so the real POL-01/POL-02
engine is exercised through the public Applications check port. Composition never replaces
the base policy; conflicts are hard holds, never last-writer-wins.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

from strongstart_contracts import Provenance, ProvenanceClass
from strongstart_contracts.answers import CheckReport
from strongstart_contracts.skills import (
    PracticeRule,
    PreferredTermRule,
    ProtectedNameRule,
    RuleTestCase,
    RuleTestReport,
    ScanFinding,
)

from ..applications.rules.policy import ProtectedName, TerminologyRule, WritingPolicy
from .compiler import canonical
from .demo import ContextDef

TESTER_VERSION = "c4-rule-tests/1"
Checker = Callable[[str, WritingPolicy | None], CheckReport]


def compose(
    base: WritingPolicy | None, rules: Sequence[PracticeRule], context: ContextDef, release: str
) -> WritingPolicy:
    terms = [
        TerminologyRule(
            rule_id=r.rule_id,
            scope=context.program,
            forbidden_term=r.forbidden_term,
            preferred_term=r.preferred_term,
        )
        for r in rules
        if isinstance(r, PreferredTermRule)
    ]
    names = [
        ProtectedName(rule_id=r.rule_id, full_name=r.full_name, acronym=r.acronym)
        for r in rules
        if isinstance(r, ProtectedNameRule)
    ]
    simulated = context.is_simulated or bool(base and base.provenance.is_simulated)
    return WritingPolicy(
        policy_id=f"{base.policy_id if base else 'no-base-policy'}+{release}",
        policy_version=base.policy_version if base else "0",
        provenance=Provenance(
            provenance_class=ProvenanceClass.SIMULATED if simulated else ProvenanceClass.SUPPLIED,
            is_simulated=simulated,
            note="Base writing policy plus an activated C4 practice (working preview only).",
        ),
        terminology_rules=[*(base.terminology_rules if base else []), *terms],
        protected_names=[*(base.protected_names if base else []), *names],
    )


def conflicts(base: WritingPolicy | None, rules: Sequence[PracticeRule]) -> list[ScanFinding]:
    out: list[ScanFinding] = []
    if base is None:
        return out
    for r in rules:
        if not isinstance(r, PreferredTermRule):
            continue
        for b in base.terminology_rules:
            same_forbidden = b.forbidden_term.casefold() == r.forbidden_term.casefold()
            reversed_rule = b.forbidden_term.casefold() == r.preferred_term.casefold()
            if (same_forbidden and b.preferred_term != r.preferred_term) or reversed_rule:
                out.append(
                    ScanFinding(
                        finding_id=f"conflict-{len(out) + 1}",
                        severity="block",
                        category="policy_conflict",
                        part=f"rule:{r.rule_id}",
                        location=f"base_policy:{b.rule_id}",
                        message=(
                            f'Conflicts with the base policy, which says use "{b.preferred_term}" '
                            f'instead of "{b.forbidden_term}". Resolve the source; no '
                            "last-writer-wins."
                        ),
                        excerpt=f"{r.forbidden_term} -> {r.preferred_term}",
                    )
                )
    return out


def _flags(report: CheckReport, check: str, rule_id: str) -> bool:
    return any(
        f.result.rule_id == check
        and f.result.outcome == "fail"
        and rule_id in (f.result.reasons or [])
        for f in report.findings
    )


def run_rule_tests(
    rules: Sequence[PracticeRule], context: ContextDef, base: WritingPolicy | None, check: Checker
) -> RuleTestReport:
    policy = compose(base, rules, context, "rule-test")
    cases: list[RuleTestCase] = []

    def case(rule_id: str, sample: str, check_id: str, expect_flag: bool, label: str) -> None:
        flagged = _flags(check(sample, policy), check_id, rule_id)
        cases.append(
            RuleTestCase(
                case_id=f"{rule_id}:{len(cases) + 1}",
                rule_id=rule_id,
                sample=sample,
                expectation=label,
                passed=flagged == expect_flag,
            )
        )

    program = context.program
    for r in rules:
        if isinstance(r, PreferredTermRule):
            f, p = r.forbidden_term, r.preferred_term
            case(
                r.rule_id,
                f"The {program} welcomes {f}s every week.",
                "POL-01",
                True,
                f'"{f}" (plural) is flagged with "{p}"',
            )
            case(
                r.rule_id,
                f"The {program} welcomes {p} every week.",
                "POL-01",
                False,
                f'"{p}" passes',
            )
            case(
                r.rule_id,
                f'The {program} once quoted a parent: "{f}".',
                "POL-01",
                False,
                "quoted wording is left as is",
            )
        else:
            n = r.full_name
            case(
                r.rule_id,
                f"Families join {n.lower()} at the {program}.",
                "POL-02",
                True,
                "a case variant of the registered name is flagged",
            )
            case(
                r.rule_id,
                f"Families join {n} at the {program}.",
                "POL-02",
                False,
                "the exact registered name passes",
            )
    body = canonical([TESTER_VERSION, *[c.model_dump(mode="json") for c in cases]])
    return RuleTestReport(
        tester_version=TESTER_VERSION,
        report_sha256=hashlib.sha256(body.encode()).hexdigest(),
        cases=cases,
        passed=bool(cases) and all(c.passed for c in cases),
    )
