import textwrap
from pathlib import Path

import pytest
from fixit import Config, Invalid, LintRule, Valid
from fixit.engine import LintRunner

from algorithms_keeper.parser.rules import (
    NamingConventionRule,
    RequireDescriptiveNameRule,
    RequireDoctestRule,
    RequireTypeHintRule,
    UseFstringRule,
)

GenTestCaseType = tuple[type[LintRule], Valid | Invalid, str]

# Test every custom rule against its embedded examples.
CUSTOM_RULES: set[type[LintRule]] = {
    NamingConventionRule,
    RequireDoctestRule,
    RequireDescriptiveNameRule,
    RequireTypeHintRule,
    UseFstringRule,
}


def _parametrized_id(obj: object) -> str:
    if isinstance(obj, type):
        return obj.__name__
    elif isinstance(obj, str):
        return obj
    else:
        return ""


def _dedent(src: str) -> str:
    """Remove the leading newline, if present, and all the common leading whitespace
     from every line in `src`.

    This can be used to make triple-quoted strings line up with the left edge of the
    display, while still presenting them in the source code in indented form.
    """
    if src[0] == "\n":
        src = src[1:]
    return textwrap.dedent(src)


def _gen_all_test_cases(rules: set[type[LintRule]]) -> list[GenTestCaseType]:
    """Generate all the test cases for the provided rules."""
    cases: list[Valid | Invalid] | None
    all_cases: list[GenTestCaseType] = []
    for rule in rules:
        if not issubclass(rule, LintRule):
            continue
        for test_type in ("VALID", "INVALID"):
            if cases := getattr(rule, test_type, None):
                for index, test_case in enumerate(cases):
                    all_cases.append((rule, test_case, f"{test_type}_{index}"))
    return all_cases


@pytest.mark.parametrize(
    "rule, test_case, test_case_id",
    _gen_all_test_cases(CUSTOM_RULES),
    ids=_parametrized_id,
)
def test_rules(
    rule: type[LintRule],
    test_case: Valid | Invalid,
    test_case_id: str,
) -> None:
    """Test all the rules with the generated test cases.

    All the test cases comes directly from the `VALID` and `INVALID` attributes for the
    provided rules. Some of the points to keep in mind:

    - Invalid test case should be written so as to generate only one report.
    - Attributes should be in all caps: `INVALID` and `VALID`
    - The code can be written in triple quoted string with indented blocks, they will
      be removed with the helper function: ``_dedent``

    """
    path = Path("example.py")
    runner = LintRunner(path, _dedent(test_case.code).encode("utf-8"))
    reports = list(runner.collect_violations([rule()], Config(path=path, enable=[])))

    if isinstance(test_case, Valid):
        assert len(reports) == 0, (
            'Expected zero reports for this "valid" test case. Instead, found:\n'
            + "\n".join(str(e) for e in reports),
        )
    else:
        assert len(reports) > 0, (
            'Expected a report for this "invalid" test case but `self.report` was '
            "not called:\n" + test_case.code,
        )
        assert len(reports) <= 1, (
            'Expected one report from this "invalid" test case. Found multiple:\n'
            "\n".join(str(e) for e in reports),
        )

        report = reports[0]

        if test_case.range is not None:
            assert test_case.range == report.range
        assert report.rule_name == rule().name

        if test_case.expected_message is not None:
            assert test_case.expected_message == report.message, (
                f"Expected message:\n    {test_case.expected_message}\n"
                f"But got:\n    {report.message}"
            )

        replacement = report.replacement
        expected_replacement = test_case.expected_replacement

        if replacement is None:
            assert expected_replacement is None, (
                "The rule for this test case has no auto-fix, but expected source was "
                "specified."
            )
            return

        assert expected_replacement is not None, (
            "The rule for this test case has an auto-fix, but no expected source was "
            "specified."
        )

        expected_replacement = _dedent(expected_replacement)
        patched_code = runner.apply_replacements(reports).code

        assert patched_code == expected_replacement, (
            "Auto-fix did not produce expected result.\n"
            f"Expected:\n{expected_replacement}\n"
            f"But found:\n{patched_code}"
        )
