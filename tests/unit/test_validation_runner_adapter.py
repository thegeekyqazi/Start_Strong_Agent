from strongstart_api.features.validation.registry import run_rule_functions


def _first(value: str) -> list[str]:
    return [f"first:{value}"]


def _second(value: str) -> list[str]:
    return [f"second:{value}", "tail"]


def test_shared_runner_preserves_c_owned_order_and_output() -> None:
    rules = (_first, _second)
    legacy = [finding for rule in rules for finding in rule("context")]
    assert run_rule_functions(rules, "context") == legacy
