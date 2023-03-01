from typing import Union

import libcst as cst
from fixit import CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

MESSAGE: str = "Please provide descriptive name for the {nodetype}: `{nodename}`"


class RequireDescriptiveNameRule(CstLintRule):
    VALID = [
        Valid(
            """
            class DescriptiveName:
                pass
            """
        ),
        Valid(
            """
            class ThisClass:
                def this_method(self):
                    pass
            """
        ),
        Valid(
            """
            def descriptive_function():
                pass
            """
        ),
        Valid(
            """
            def function(descriptive, parameter):
                pass
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            class T:
                pass
            """
        ),
        Invalid(
            """
            class ThisClass:
                def m(self):
                    pass
            """
        ),
        Invalid(
            """
            def f():
                pass
            """
        ),
        Invalid(
            """
            def fun(a):
                pass
            """
        ),
    ]

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self._validate_name_length(node, "class")

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._validate_name_length(node, "function")

    def visit_Param(self, node: cst.Param) -> None:
        self._validate_name_length(node, "parameter")

    def _validate_name_length(
        self, node: Union[cst.ClassDef, cst.FunctionDef, cst.Param], nodetype: str
    ) -> None:
        nodename = node.name.value
        if len(nodename) == 1:
            self.report(
                node, message=MESSAGE.format(nodetype=nodetype, nodename=nodename)
            )
