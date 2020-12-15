import textwrap
from pathlib import Path
from typing import List, Optional, Tuple, Type, Union

import pytest
from fixit import CstLintRule
from fixit.common.utils import InvalidTestCase, LintRuleCollectionT, ValidTestCase
from fixit.rule_lint_engine import lint_file

from algorithms_keeper.parser.python_parser import get_rules_from_config

GenTestCaseType = Tuple[Type[CstLintRule], Union[ValidTestCase, InvalidTestCase], str]


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


def _gen_all_test_cases(rules: LintRuleCollectionT) -> List[GenTestCaseType]:
    """Generate all the test cases for the provided rules."""
    cases: Optional[List[Union[ValidTestCase, InvalidTestCase]]]
    all_cases: List[GenTestCaseType] = []
    for rule in rules:
        if not issubclass(rule, CstLintRule):
            continue
        for test_type in {"VALID", "INVALID"}:
            if cases := getattr(rule, test_type, None):
                for index, test_case in enumerate(cases):
                    all_cases.append((rule, test_case, f"{test_type}_{index}"))
    return all_cases


@pytest.mark.parametrize(
    "rule, test_case, test_case_id",
    _gen_all_test_cases(get_rules_from_config()),
    ids=_parametrized_id,
)
def test_rules(
    rule: Type[CstLintRule],
    test_case: Union[ValidTestCase, InvalidTestCase],
    test_case_id: str,
) -> None:
    """Test all the rules with the generated test cases.

    All the test cases comes directly from the `VALID` and `INVALID` attributes for the
    provided rules. Some of the points to keep in mind:

    - Invalid test case should be written so as to generate only one report.
    - Attributes should be in all caps: `INVALID` and `VALID`
    - The code can be written in triple quoted string with indented blocks, they will
      be removed with the helper function: ``_dedent``

    The logic of the code is the same as that of ``fixit.common.testing`` but this has
    been converted to using ``pytest`` and removed the fixture feature. This might be
    added if there's any need for that in the future.
    """
    reports = lint_file(
        Path(test_case.filename),
        _dedent(test_case.code).encode("utf-8"),
        config=test_case.config,
        rules={rule},
    )

    if isinstance(test_case, ValidTestCase):
        assert len(reports) == 0
    else:
        assert 0 < len(reports) <= 1

        report = reports[0]  # type: ignore

        if test_case.line is not None:
            assert test_case.line == report.line
        if test_case.column is not None:
            assert test_case.column == report.column

        kind = test_case.kind if test_case.kind is not None else rule.__name__
        assert kind == report.code

        if test_case.expected_message is not None:
            assert test_case.expected_message == report.message

        patch = report.patch
        expected_replacement = test_case.expected_replacement

        if patch is None:
            assert expected_replacement is None
        else:
            assert expected_replacement is not None
            expected_replacement = _dedent(expected_replacement)
            patched_code = patch.apply(_dedent(test_case.code))
            assert patched_code == expected_replacement
