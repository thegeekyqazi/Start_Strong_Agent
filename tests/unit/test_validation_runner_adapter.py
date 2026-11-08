from strongstart_api.features.validation.registry import run_rule_functions


def test_shared_runner_preserves_c_owned_order_and_output() -> None:
    rules = (lambda value: [f"first:{value}"], lambda value: [f"second:{value}", "tail"])
    legacy = [finding for rule in rules for finding in rule("context")]
    assert run_rule_functions(rules, "context") == legacy
