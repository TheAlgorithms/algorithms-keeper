from typing import Set

import libcst as cst
from fixit import CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

MISSING_TYPE_HINT: str = "Please provide type hint for the parameter: `{nodename}`"

MISSING_RETURN_TYPE_HINT: str = (
    "Please provide return type hint for the function: `{nodename}`. "
    "**If the function does not return a value, please provide "
    "the type hint as:** `def function() -> None:`"
)

IGNORE_PARAM: Set[str] = {"self", "cls"}


class RequireTypeHintRule(CstLintRule):

    VALID = [
        Valid(
            """
            def func() -> str:
                pass
            """
        ),
        Valid(
            """
            def func() -> None:
                pass
            """
        ),
        Valid(
            """
            def func(some: str, other: int) -> None:
                pass
            """
        ),
        Valid(
            """
            class Random:
                def random_method(self, value: int) -> None:
                    pass
            """
        ),
        Valid(
            """
            class Random:
                @classmethod
                def initiate(cls, value: str) -> str:
                    pass
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            def func():
                pass
            """
        ),
        Invalid(
            """
            def func(num: int, val: str):
                pass
            """
        ),
        Invalid(
            """
            def func(num: int, val) -> None:
                pass
            """
        ),
        Invalid(
            """
            class Random:
                def __init__(self, val) -> None:
                    pass
            """
        ),
        Invalid(
            """
            class Random:
                @classmethod
                def from_class(cls, val) -> None:
                    pass
            """
        ),
    ]

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if node.returns is None:
            self.report(node, MISSING_RETURN_TYPE_HINT.format(nodename=node.name.value))

    def visit_Param(self, node: cst.Param) -> None:
        nodename = node.name.value
        if node.annotation is None and nodename not in IGNORE_PARAM:
            self.report(node, MISSING_TYPE_HINT.format(nodename=nodename))
