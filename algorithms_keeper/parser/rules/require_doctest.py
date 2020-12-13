from typing import Union

import libcst as cst
from fixit import CstContext, CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid
from libcst.metadata.scope_provider import Assignment, GlobalScope, ScopeProvider

DoctestNodeT = Union[cst.Module, cst.ClassDef, cst.FunctionDef]

MISSING_DOCTEST: str = (
    "As there is no test file in this pull request nor any test function or class in "
    "the file `{filepath}`, please provide doctest for the function `{nodename}`"
)

INIT: str = "__init__"


class RequireDoctestRule(CstLintRule):

    METADATA_DEPENDENCIES = (ScopeProvider,)

    VALID = [
        Valid(
            """
            '''
            Module-level docstring contains doctest
            >>> foo()
            None
            '''
            def foo():
                pass

            class Bar:
                def baz(self):
                    pass

            def bar():
                pass
            """
        ),
        Valid(
            """
            def foo():
                pass

            def bar():
                pass

            # Contains a test function
            def test_foo():
                pass

            class Baz:
                def baz(self):
                    pass

            def spam():
                pass
            """
        ),
        Valid(
            """
            def foo():
                pass

            class Baz:
                def baz(self):
                    pass

            def bar():
                pass

            # Contains a test class
            class TestSpam:
                def test_spam(self):
                    pass

            def egg():
                pass
            """
        ),
        Valid(
            """
            def foo():
                '''
                >>> foo()
                '''
                pass

            class Spam:
                '''
                Class-level docstring contains doctest
                >>> Spam()
                '''
                def foo(self):
                    pass

                def spam(self):
                    pass

            def bar():
                '''
                >>> bar()
                '''
                pass
            """
        ),
        Valid(
            """
            def spam():
                '''
                >>> spam()
                '''
                pass

            class Bar:
                # No doctest needed for the init function
                def __init__(self):
                    pass

                def bar(self):
                    '''
                    >>> bar()
                    '''
                    pass
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            def bar():
                pass
            """
        ),
        Invalid(
            """
            class Bar:
                def __init__(self):
                    pass

                def bar(self):
                    pass
            """
        ),
        Invalid(
            """
            def bar():
                '''
                >>> bar()
                '''
                pass

            class Spam:
                '''
                >>> Spam()
                '''
                def spam():
                    pass

            # Check that the `skip_doctest` attribute is reseted after leaving the class
            def egg():
                pass
            """
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self.skip_doctest: bool = False
        self.__temp: bool = False

    def visit_Module(self, node: cst.Module) -> None:
        self.skip_doctest = (
            True if self.contains_testnode(node) else self.contains_doctest(node)
        )

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.__temp = self.skip_doctest
        self.skip_doctest = self.contains_doctest(node)

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self.skip_doctest = self.__temp

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        nodename = node.name.value
        if (
            nodename != INIT
            and not self.skip_doctest
            and not self.contains_doctest(node)
        ):
            self.report(
                node,
                MISSING_DOCTEST.format(
                    filepath=self.context.file_path, nodename=nodename
                ),
            )

    def contains_doctest(self, node: DoctestNodeT) -> bool:
        if not self.skip_doctest:
            docstring = node.get_docstring()
            if docstring is not None:
                for line in docstring.splitlines():
                    if line.strip().startswith(">>> "):
                        return True
            return False
        return True

    def contains_testnode(self, node: cst.Module) -> bool:
        scope: GlobalScope = self.get_metadata(ScopeProvider, node)
        for assignment in scope.assignments:
            if isinstance(assignment, Assignment):
                assigned_node = assignment.node
                if (
                    isinstance(assigned_node, cst.FunctionDef)
                    and assigned_node.name.value.startswith("test_")
                ) or (
                    isinstance(assigned_node, cst.ClassDef)
                    and assigned_node.name.value.startswith("Test")
                ):
                    return True
        return False
