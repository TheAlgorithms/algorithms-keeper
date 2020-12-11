import ast
from typing import Tuple, Union

from algorithms_keeper.constants import Missing
from algorithms_keeper.parser.record import PullRequestReviewRecord
from algorithms_keeper.utils import File

DoctestNodeT = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module]
AnyFunctionT = Union[ast.FunctionDef, ast.AsyncFunctionDef]


class PullRequestFileNodeVisitor(ast.NodeVisitor):
    """Main Visitor class to visit all the nodes in the given file.

    This class needs to be initialized for every valid file in the given pull request.
    The Parser will be using this class to visit all the nodes as it walks down the
    abstract syntax tree for the given file.

    Every node will have its predefined set of rules which, if not satisfied, will be
    reported to the given reporter (self.reporter). Rules related to each node type is
    listed in the docstring of the same visitor function.

    From ``ast.NodeVisitor``:
    Per default the visitor functions for the nodes are ``'visit_'`` + class name of
    the node.  So a `TryFinally` node visit function would be `visit_TryFinally`. This
    behavior can be changed by overriding the `visit` method. If no visitor function
    exists for a node (return value `None`) the `generic_visit` visitor is used instead.
    """

    def __init__(
        self, file: File, record: PullRequestReviewRecord, skip_doctest: bool
    ) -> None:
        self.record = record
        self.file = file
        self.skip_doctest = skip_doctest

    def visit(self, node: ast.AST) -> None:
        """Visit a node only if the `visit` function is defined."""
        method = "visit_" + node.__class__.__name__
        # There's no need to perform a ``generic_visit`` everytime a node function
        # is not present.
        visitor = getattr(self, method, None)
        if visitor is not None:
            visitor(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_anyfunction(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_anyfunction(node)

    def _visit_anyfunction(self, function: AnyFunctionT) -> None:
        """Visit the sync/async function node.

        Rules:

        - Function name should be of length > 1.
        - Other than ``__init__``, all the other functions should contain doctest. If
          the function does not contain the docstring, then that will be considered as
          ``doctest`` not present.
        - Function should have a valid return annotation. If the function returns
          ``None``, then the function should contain the return annotation as:
          ``def function() -> None:``
        """
        nodedata = self._nodedata(function)
        if len(function.name) == 1:
            self.record.add_comment(*nodedata, Missing.DESCRIPTIVE_NAME)
        if function.name != "__init__" and not self._contains_doctest(function):
            self.record.add_comment(*nodedata, Missing.DOCTEST)
        self.generic_visit(function.args)
        if function.returns is None:
            self.record.add_comment(*nodedata, Missing.RETURN_TYPE_HINT)

    def visit_arg(self, arg: ast.arg) -> None:
        """Visit the argument node. The argument can be positional-only, keyword-only or
        postitional/keyword.

        Rules:

        - Argument name should be of length > 1.
        - Argument should contain a valid annotation.
        """
        nodedata = self._nodedata(arg)
        if len(arg.arg) == 1:
            self.record.add_comment(*nodedata, Missing.DESCRIPTIVE_NAME)
        if arg.arg != "self" and arg.annotation is None:
            self.record.add_comment(*nodedata, Missing.TYPE_HINT)

    def visit_ClassDef(self, klass: ast.ClassDef) -> None:
        """Visit the class node.

        Rules:

        - Class name should be of length > 1.
        - If a class contains doctest in the class-level docstring, doctest checking
          will be skipped for all its methods.
        """
        if len(klass.name) == 1:
            self.record.add_comment(*self._nodedata(klass), Missing.DESCRIPTIVE_NAME)
        temp = self.skip_doctest
        if not self.skip_doctest and self._contains_doctest(klass):
            self.skip_doctest = True
        # Make a visit to all the methods in a class after checking whether the class
        # contains doctest or not.
        self.generic_visit(klass)
        self.skip_doctest = temp

    def _contains_doctest(self, node: DoctestNodeT) -> bool:
        if not self.skip_doctest:
            docstring = ast.get_docstring(node)
            if docstring is not None:
                for line in docstring.splitlines():
                    if line.strip().startswith(">>> "):
                        return True
            return False
        return True

    def _nodedata(self, node: ast.AST) -> Tuple[str, int, str, str]:
        """Helper function to fill data required in the ``Comment`` object as per the
        given node."""
        if isinstance(node, ast.ClassDef):
            data = self.file.name, node.lineno, node.name, "class"
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            data = self.file.name, node.lineno, node.name, "function"
        elif isinstance(node, ast.arg):
            data = self.file.name, node.lineno, node.arg, "parameter"
        return data
