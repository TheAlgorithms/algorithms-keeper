from typing import Union

import libcst as cst
import libcst.matchers as m
from fixit import CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

INVALID_CAMEL_CASE_NAME: str = (
    "Class names should follow the [`CamelCase`]"
    + "(https://en.wikipedia.org/wiki/Camel_case) naming convention. "
    + "Please update the name of the class `{nodename}` accordingly. "
    + "Examples: `Oneword`, `MultipleWords`, etc."
)

INVALID_SNAKE_CASE_NAME: str = (
    "Variable and function names should follow the [`snake_case`]"
    + "(https://en.wikipedia.org/wiki/Snake_case) naming convention. "
    + "Please update the name of the {nodetype} `{nodename}` accordingly. "
    + "Examples: `oneword`, `multiple_words_seperated_by_underscore`, etc."
)


def _any_uppercase_letter(name: str) -> bool:
    for letter in name:
        if letter.isupper():
            return True
    return False


class NamingConventionRule(CstLintRule):

    VALID = [
        Valid("type_hint: str"),
        Valid("type_hint_var: int = 5"),
        Valid("hello = 'world'"),
        Valid("snake_case = 'assign'"),
        Valid("for iteration in range(5): pass"),
        Valid("class SomeClass: pass"),
        Valid("class One: pass"),
        Valid("def oneword(): pass"),
        Valid("def some_extra_words(): pass"),
        Valid("all = names_are = valid_in_multiple_assign = 5"),
        Valid("(walrus := 'operator')"),
    ]

    INVALID = [
        Invalid("type_Hint_Var: int = 5"),
        Invalid("Hello = 'world'"),
        Invalid("ranDom_UpPercAse = 'testing'"),
        Invalid("for RandomCaps in range(5): pass"),
        Invalid("class lowerPascalCase: pass"),
        Invalid("class all_lower_case: pass"),
        Invalid("def oneWordInvalid(): pass"),
        Invalid("def Pascal_Case(): pass"),
        Invalid("valid = another_valid = Invalid = 5"),
        Invalid("(waLRus := 'operator')"),
    ]

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        nodename = node.name.value
        if nodename[0].islower() or "_" in nodename:
            self.report(node, INVALID_CAMEL_CASE_NAME.format(nodename=nodename))

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if node.value is not None:
            self._validate_snake_case_name(node, "variable")

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        self._validate_snake_case_name(node, "variable")

    def visit_For(self, node: cst.For) -> None:
        self._validate_snake_case_name(node, "variable")

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._validate_snake_case_name(node, "function")

    def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
        self._validate_snake_case_name(node, "variable")

    def _validate_snake_case_name(
        self,
        node: Union[
            cst.AnnAssign, cst.AssignTarget, cst.For, cst.FunctionDef, cst.NamedExpr
        ],
        nodetype: str,
    ) -> None:
        namekey: str = "nodename"
        extracted = m.extract(
            node,
            m.FunctionDef(
                name=m.Name(
                    value=m.SaveMatchedNode(
                        m.MatchIfTrue(_any_uppercase_letter), namekey
                    )
                )
            ),
        ) or m.extract(
            node,
            m.TypeOf(m.AnnAssign, m.AssignTarget, m.For, m.NamedExpr)(
                target=m.Name(
                    value=m.SaveMatchedNode(
                        m.MatchIfTrue(_any_uppercase_letter), namekey
                    )
                )
            ),
        )

        if extracted is not None:
            self.report(
                node,
                INVALID_SNAKE_CASE_NAME.format(
                    nodetype=nodetype, nodename=extracted[namekey]
                ),
            )
