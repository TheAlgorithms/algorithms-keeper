from enum import Enum
from typing import Collection, Optional

import libcst as cst
import libcst.matchers as m
from fixit import CstContext, CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid
from libcst.metadata import QualifiedName, QualifiedNameProvider

INVALID_CAMEL_CASE_NAME_COMMENT: str = (
    "Class names should follow the [`CamelCase`]"
    "(https://en.wikipedia.org/wiki/Camel_case) naming convention. "
    "Please update the following name accordingly: `{nodename}`"
)

INVALID_SNAKE_CASE_NAME_COMMENT: str = (
    "Variable and function names should follow the [`snake_case`]"
    "(https://en.wikipedia.org/wiki/Snake_case) naming convention. "
    "Please update the following name accordingly: `{nodename}`"
)


class NamingConvention(Enum):
    CAMEL_CASE = INVALID_CAMEL_CASE_NAME_COMMENT
    SNAKE_CASE = INVALID_SNAKE_CASE_NAME_COMMENT

    def valid(self, name: str) -> bool:
        """Check whether the provided *name* conforms as per the naming convention
        the method was called on.

        Returns ``True`` if it is valid otherwise ``False``.
        """
        if self is NamingConvention.CAMEL_CASE:
            name = name.strip("_")
            if name[0].islower() or "_" in name:
                return False
        elif name.lower() != name and name.upper() != name:
            return False
        return True


class NamingConventionRule(CstLintRule):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)  # type: ignore

    VALID = [
        Valid("type_hint: str"),
        Valid("type_hint_var: int = 5"),
        Valid("CONSTANT_WITH_UNDERSCORE12 = 10"),
        Valid("hello = 'world'"),
        Valid("snake_case = 'assign'"),
        Valid("for iteration in range(5): pass"),
        Valid("class _PrivateClass: pass"),
        Valid("class SomeClass: pass"),
        Valid("class One: pass"),
        Valid("def oneword(): pass"),
        Valid("def some_extra_words(): pass"),
        Valid("all = names_are = valid_in_multiple_assign = 5"),
        Valid("(walrus := 'operator')"),
        Valid("multiple, valid, assignments = 1, 2, 3"),
        Valid(
            """
            class Spam:
                def __init__(self, valid, another_valid):
                    self.valid = valid
                    self.another_valid = another_valid
                    self._private = None
                    self.__extreme_private = None

                def bar(self):
                    # This is just to test that the access is not being tested.
                    return self.some_Invalid_NaMe
            """
        ),
        Valid(
            """
            from typing import List
            from collections import namedtuple

            Matrix = List[int]
            Point = namedtuple("Point", "x, y")

            some_matrix: Matrix = [1, 2]
            """
        ),
    ]

    INVALID = [
        Invalid("type_Hint_Var: int = 5"),
        Invalid("hellO = 'world'"),
        Invalid("ranDom_UpPercAse = 'testing'"),
        Invalid("for RandomCaps in range(5): pass"),
        Invalid("class _Invalid_PrivateClass: pass"),
        Invalid("class _invalidPrivateClass: pass"),
        Invalid("class lowerPascalCase: pass"),
        Invalid("class all_lower_case: pass"),
        Invalid("def oneWordInvalid(): pass"),
        Invalid("def Pascal_Case(): pass"),
        Invalid("valid = another_valid = Invalid = 5"),
        Invalid("(waLRus := 'operator')"),
        Invalid("def func(invalidParam, valid_param): pass"),
        Invalid("multiple, inValid, assignments = 1, 2, 3"),
        Invalid("[inside, list, inValid] = Invalid, 2, 3"),
        Invalid(
            """
            class Spam:
                def __init__(self, foo, bar):
                    self.foo = foo
                    self._Bar = bar
            """
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self._assigntarget_counter: int = 0

    def visit_Assign(self, node: cst.Assign) -> None:
        metadata: Optional[Collection[QualifiedName]] = self.get_metadata(
            QualifiedNameProvider, node.value, None
        )

        if metadata is not None:
            for qualname in metadata:
                # If the assignment is done with some objects from the typing or
                # collections module, then we will skip the check as the assignment
                # could be a type alias or the variable could be a class made using
                # ``collections.namedtuple``.
                if qualname.name.startswith(("typing", "collections")):
                    return None

        for target_node in node.targets:
            if m.matches(target_node, m.AssignTarget(target=m.Name())):
                nodename = cst.ensure_type(target_node.target, cst.Name).value
                self._validate_nodename(node, nodename, NamingConvention.SNAKE_CASE)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        # The assignment value is optional, as it is possible to annotate an
        # expression without assigning to it: ``var: int``
        if m.matches(
            node,
            m.AnnAssign(
                target=m.Name(), value=m.MatchIfTrue(lambda value: value is not None)
            ),
        ):
            nodename = cst.ensure_type(node.target, cst.Name).value
            self._validate_nodename(node, nodename, NamingConvention.SNAKE_CASE)

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        self._assigntarget_counter += 1

    def leave_AssignTarget(self, node: cst.AssignTarget) -> None:
        self._assigntarget_counter -= 1

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self._validate_nodename(node, node.name.value, NamingConvention.CAMEL_CASE)

    def visit_Attribute(self, node: cst.Attribute) -> None:
        # The attribute node can come through other context as well but we only care
        # about the ones coming from assignments.
        if self._assigntarget_counter > 0:  # noqa: SIM102
            # We only care about assignment attribute to *self*.
            if m.matches(node, m.Attribute(value=m.Name(value="self"))):
                self._validate_nodename(
                    node, node.attr.value, NamingConvention.SNAKE_CASE
                )

    def visit_Element(self, node: cst.Element) -> None:
        # We only care about elements in *List* or *Tuple* specifically coming from
        # inside the multiple assignments.
        if self._assigntarget_counter > 0:  # noqa: SIM102
            if m.matches(node, m.Element(value=m.Name())):
                nodename = cst.ensure_type(node.value, cst.Name).value
                self._validate_nodename(node, nodename, NamingConvention.SNAKE_CASE)

    def visit_For(self, node: cst.For) -> None:
        if m.matches(node, m.For(target=m.Name())):
            nodename = cst.ensure_type(node.target, cst.Name).value
            self._validate_nodename(node, nodename, NamingConvention.SNAKE_CASE)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._validate_nodename(node, node.name.value, NamingConvention.SNAKE_CASE)

    def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
        if m.matches(node, m.NamedExpr(target=m.Name())):
            nodename = cst.ensure_type(node.target, cst.Name).value
            self._validate_nodename(node, nodename, NamingConvention.SNAKE_CASE)

    def visit_Param(self, node: cst.Param) -> None:
        self._validate_nodename(node, node.name.value, NamingConvention.SNAKE_CASE)

    def _validate_nodename(
        self, node: cst.CSTNode, nodename: str, naming_convention: NamingConvention
    ) -> None:
        """Validate the provided *nodename* as per the given *naming_convention*.

        This is a convenience method as the same steps will be repeated for every
        visit functions which are to validate the name and report if found invalid.
        """
        if not naming_convention.valid(nodename):
            self.report(node, naming_convention.value.format(nodename=nodename))
