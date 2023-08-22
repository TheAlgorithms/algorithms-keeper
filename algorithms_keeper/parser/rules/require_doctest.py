from typing import Union

import libcst as cst
import libcst.matchers as m
from fixit import CstContext, CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

MISSING_DOCTEST: str = (
    "As there is no test file in this pull request nor any test function or class in "
    "the file `{filepath}`, please provide doctest for the function `{nodename}`"
)

INIT: str = "__init__"


class RequireDoctestRule(CstLintRule):
    VALID = [
        # Module-level docstring contains doctest.
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
        # Module contains a test function.
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
        # Module contains multiple test function.
        Valid(
            """
            def foo():
                pass

            def bar():
                pass

            def test_foo():
                pass

            def test_bar():
                pass

            class Baz:
                def baz(self):
                    pass

            def spam():
                pass
            """
        ),
        # Module contains a test class.
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
        # Class level docstring contains doctest, so skip doctest checking only
        # for that class.
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
        # No doctest required for the ``__init__`` function.
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
        # No doctest required in the ``web_programming`` directory.
        Valid(
            """
            def foo():
                pass
            """,
            filename="web_programming/foo.py",
        ),
    ]

    INVALID = [
        Invalid(
            """
            def bar():
                pass
            """
        ),
        # Only the ``__init__`` function does not require doctest.
        Invalid(
            """
            def foo():
                '''
                >>> foo()
                '''
                pass

            class Spam:
                def __init__(self):
                    pass

                def spam(self):
                    pass
            """
        ),
        # Check that `_skip_doctest` attribute is reset after leaving the class.
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

            def egg():
                pass
            """
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self._skip_doctest: bool = False
        self._temporary: bool = False

    def should_skip_file(self) -> bool:
        return self.context.file_path.match("web_programming/*")

    def visit_Module(self, node: cst.Module) -> None:
        self._skip_doctest = self._has_testnode(node) or self._has_doctest(node)

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        # Temporary storage of the ``skip_doctest`` value only during the class visit.
        # If the class-level docstring contains doctest, then the checks should only be
        # skipped for all its methods and not for other functions/class in the module.
        # After leaving the class, ``skip_doctest`` should be reset to whatever the
        # value was before.
        self._temporary = self._skip_doctest
        self._skip_doctest = self._has_doctest(node)

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self._skip_doctest = self._temporary

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        nodename = node.name.value
        if nodename != INIT and not self._has_doctest(node):
            self.report(
                node,
                MISSING_DOCTEST.format(
                    filepath=self.context.file_path, nodename=nodename
                ),
            )

    def _has_doctest(
        self, node: Union[cst.Module, cst.ClassDef, cst.FunctionDef]
    ) -> bool:
        """Check whether the given node contains doctests.

        If the ``_skip_doctest`` attribute is ``True``, the function will by default
        return ``True``, otherwise it will extract the docstring and look for doctest
        patterns (>>> ) in it. If there is no docstring for the node, this will mean
        the absence of doctest.
        """
        if not self._skip_doctest:
            docstring = node.get_docstring()
            if docstring is not None:
                for line in docstring.splitlines():
                    if line.strip().startswith(">>> "):
                        return True
            return False
        return True

    @staticmethod
    def _has_testnode(node: cst.Module) -> bool:
        return m.matches(
            node,
            m.Module(
                body=[
                    # Sequence wildcard matchers matches LibCAST nodes in a row in a
                    # sequence. It does not implicitly match on partial sequences. So,
                    # when matching against a sequence we will need to provide a
                    # complete pattern. This often means using helpers such as
                    # ``ZeroOrMore()`` as the first and last element of the sequence.
                    m.ZeroOrMore(),
                    m.AtLeastN(
                        n=1,
                        matcher=m.OneOf(
                            m.FunctionDef(
                                name=m.Name(
                                    value=m.MatchIfTrue(
                                        lambda value: value.startswith("test_")
                                    )
                                )
                            ),
                            m.ClassDef(
                                name=m.Name(
                                    value=m.MatchIfTrue(
                                        lambda value: value.startswith("Test")
                                    )
                                )
                            ),
                        ),
                    ),
                    m.ZeroOrMore(),
                ]
            ),
        )
