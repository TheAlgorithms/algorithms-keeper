from typing import Dict, Optional, Sequence, Union

import libcst as cst
import libcst.matchers as m
from fixit import CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

CAMEL_CASE: str = (
    "Class names should follow the [`CamelCase`]"
    + "(https://en.wikipedia.org/wiki/Camel_case) naming convention. "
    + "Please update the name `{nodename}` accordingly. "
    + "Examples: `Oneword`, `MultipleWords`, etc."
)

SNAKE_CASE: str = (
    "Variable and function names should follow the [`snake_case`]"
    + "(https://en.wikipedia.org/wiki/Snake_case) naming convention. "
    + "Please update the name `{nodename}` accordingly. "
    + "Examples: `oneword`, `multiple_words_seperated_by_underscore`, etc."
)


def _any_uppercase_letter(name: str) -> bool:
    for letter in name:
        if letter.isupper():
            return True
    return False


class NamingConventionRule(CstLintRule):

    VALID = [
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
            self.report(node, CAMEL_CASE.format(nodename=nodename))

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if (
            node.value is not None
            and (extracted := self._extract_invalid_node(node)) is not None
        ):
            self.report(node, SNAKE_CASE.format(nodename=extracted["nodename"]))

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        if (extracted := self._extract_invalid_node(node)) is not None:
            self.report(node, SNAKE_CASE.format(nodename=extracted["nodename"]))

    def visit_For(self, node: cst.For) -> None:
        if (extracted := self._extract_invalid_node(node)) is not None:
            self.report(node, SNAKE_CASE.format(nodename=extracted["nodename"]))

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if (extracted := self._extract_invalid_node(node)) is not None:
            self.report(node, SNAKE_CASE.format(nodename=extracted["nodename"]))

    def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
        if (extracted := self._extract_invalid_node(node)) is not None:
            self.report(node, SNAKE_CASE.format(nodename=extracted["nodename"]))

    @staticmethod
    def _extract_invalid_node(
        node: Union[
            cst.AnnAssign, cst.AssignTarget, cst.For, cst.FunctionDef, cst.NamedExpr
        ]
    ) -> Optional[Dict[str, Union[cst.CSTNode, Sequence[cst.CSTNode]]]]:
        return m.extract(
            node,
            m.FunctionDef(
                name=m.Name(
                    value=m.SaveMatchedNode(
                        m.MatchIfTrue(_any_uppercase_letter), "nodename"
                    )
                )
            ),
        ) or m.extract(
            node,
            m.TypeOf(m.AnnAssign, m.AssignTarget, m.For, m.NamedExpr)(
                target=m.Name(
                    value=m.SaveMatchedNode(
                        m.MatchIfTrue(_any_uppercase_letter), "nodename"
                    )
                )
            ),
        )
