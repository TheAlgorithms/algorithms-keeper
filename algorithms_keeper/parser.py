import ast
from dataclasses import dataclass, field
from logging import Logger
from typing import Any, Dict, List, Set, Tuple, Union

from algorithms_keeper.constants import Label
from algorithms_keeper.log import logger as main_logger
from algorithms_keeper.utils import File


@dataclass(frozen=True)
class ReviewComment:
    # Text of the review comment. This is different from the body of the review itself.
    body: str
    # The relative path to the file that necessitates a review comment.
    path: str
    # The line of the blob in the pull request diff that the comment applies to.
    line: int
    # In a split diff view, the side of the diff that the pull request's changes appear
    # on. Can be LEFT or RIGHT. Use LEFT for deletions that appear in red. Use RIGHT for
    # additions that appear in green or unchanged lines that appear in white and are
    # shown for context.
    side: str = "RIGHT"

    @property
    def asdict(self) -> Dict[str, Any]:
        """A wrapper around the ``__dict__`` attribute of ``ReviewComment`` instances.

        Useful for collecting all the comments into a list.
        """
        return self.__dict__


@dataclass(frozen=True)
class PullRequestReviewRecord:
    """A Record object to store all the ``ReviewComment`` instances.

    This should be initialized once per pull request and use the *add_* methods to
    add a ``ReviewComment`` instance to their respective group.

    All *add_* methods except the ``add_error`` have the same parameters:

    filepath: Path from the repository root to the file
    lineno: Line number in the file
    nodename: Name of the class/function/parameter
    nodetype: Type of nodename as in class/function/parameter
    side: In a split diff view, which side the node appears on (default: RIGHT)

    ``add_error`` is used to include any exceptions faced while parsing the source
    code in the parser. It requires the *message* argument which is the last part of
    the traceback message.
    """

    doctest: List[ReviewComment] = field(default_factory=list)
    annotation: List[ReviewComment] = field(default_factory=list)
    return_annotation: List[ReviewComment] = field(default_factory=list)
    descriptive_name: List[ReviewComment] = field(default_factory=list)
    error: List[ReviewComment] = field(default_factory=list)

    def add_doctest(
        self,
        filepath: str,
        lineno: int,
        nodename: str,
        nodetype: str,
        side: str = "RIGHT",
    ) -> None:
        body = f"Please provide doctest for the {nodetype}: `{nodename}`"
        self.doctest.append(ReviewComment(body, filepath, lineno, side))

    def add_annotation(
        self,
        filepath: str,
        lineno: int,
        nodename: str,
        nodetype: str,
        side: str = "RIGHT",
    ) -> None:
        body = f"Please provide type hint for the {nodetype}: `{nodename}`"
        self.annotation.append(ReviewComment(body, filepath, lineno, side))

    def add_return_annotation(
        self,
        filepath: str,
        lineno: int,
        nodename: str,
        nodetype: str,
        side: str = "RIGHT",
    ) -> None:
        body = (
            f"Please provide return type hint for the {nodetype}: `{nodename}`.\n\n"
            f"**NOTE: If the {nodetype} returns `None`, please provide the type hint "
            f"as:**\n```python\ndef function() -> None:\n```"
        )
        self.return_annotation.append(ReviewComment(body, filepath, lineno, side))

    def add_descriptive_name(
        self,
        filepath: str,
        lineno: int,
        nodename: str,
        nodetype: str,
        side: str = "RIGHT",
    ) -> None:
        body = f"Please provide descriptive name for the {nodetype}: `{nodename}`"
        self.descriptive_name.append(ReviewComment(body, filepath, lineno, side))

    def add_error(self, message: str, filepath: str, lineno: int) -> None:
        body = (
            f"An error occured while parsing the file: `{filepath}`\n"
            f"```python\n{message}\n```"
        )
        self.error.append(ReviewComment(body, filepath, lineno))

    def collect_comments(self) -> List[Dict[str, Any]]:
        """Return all the review comments in the record instance.

        This is how GitHub wants the *comments* value while creating the review.
        """
        c = []
        for comments in self.__dict__.values():
            for comment in comments:
                c.append(comment.asdict)
        return c


class PullRequestFilesParser:
    """A parser for all the pull request Python files.

    This class needs to be initialized once per pull request and use its public methods
    to process, store and access the relevant information regarding the pull request.

    This object performs no I/O of its own as the logic needs to be separated. This
    means that the function instantiating the object needs to provide the source code
    of the file to be parsed. For this, there's a helper function ``files_to_check``
    to get the list of all the valid Python files in the provided pull request. The
    user function will request the file content from GitHub and pass it to the main
    function ``parse``.
    """

    _DOCS_EXTENSIONS: Tuple[str, ...] = (".md", ".rst")

    _ACCEPTED_EXTENSIONS: Tuple[str, ...] = (
        # Configuration files
        ".ini",
        ".toml",
        ".yaml",
        ".yml",
        ".cfg",
        # Data files
        ".json",
        ".txt",
        # Good old Python file
        ".py",
    ) + _DOCS_EXTENSIONS

    def __init__(
        self,
        pr_files: List[File],
        *,
        pull_request: Dict[str, Any],
        logger: Logger = main_logger,
    ) -> None:
        self.pr_files = pr_files
        self.pull_request = pull_request
        # Extract out some useful information.
        self.pr_author = pull_request["user"]["login"]
        self.pr_labels = [label["name"] for label in pull_request["labels"]]
        self.pr_html_url = pull_request["html_url"]

        # By providing the logger to the class, we won't have to log anything from the
        # pull requests module. Defaults to ``algorithms_keeper.log.logger``
        self.logger = logger

        # Attribute to determine whether to skip doctest checking or not. This will
        # be set to ``True`` if the pull request contains a test file.
        self._skip_doctest = self._contains_testfile()

        # Attribute to store all the review data.
        self._pr_record = PullRequestReviewRecord()

        # Initiate the label attributes. These are represented as ``Set`` internally to
        # avoid the duplication of labels.
        # The parser will fill the data for each file parsed and there could be
        # same errors in multiple files resulting in the addition of the corresponding
        # labels multiple times.
        self._add_labels: Set[str] = set()
        self._remove_labels: Set[str] = set()

    @property
    def add_labels(self) -> List[str]:
        return list(self._add_labels)

    @property
    def remove_labels(self) -> List[str]:
        return list(self._remove_labels)

    def validate_extension(self) -> str:
        """Check pull request files extension. Returns an empty string if all files are
        valid otherwise a comma separated string containing the filepaths.

        A file is considered invalid if:

        - It is extensionless and is not a dotfile. NOTE: Files present only in the
          root directory will be checked for `isdotfile`.
        - File extension is not accepted in the repository.
          See: `constants.ACCEPTED_EXTENSION`

        NOTE: Extensionless files will be considered valid only if it is present in
        the ".github" directory. Eg: ".github/CODEOWNERS"
        """
        invalid_filepath = []
        for file in self.pr_files:
            filepath = file.path
            if not filepath.suffix:
                if ".github" not in filepath.parts:
                    if filepath.parent.name:
                        invalid_filepath.append(file.name)
                    # Dotfiles are not considered as invalid if they are present in the
                    # root of the repository
                    elif not filepath.name.startswith("."):
                        invalid_filepath.append(file.name)
            elif filepath.suffix not in self._ACCEPTED_EXTENSIONS:
                invalid_filepath.append(file.name)
        invalid_files = ", ".join(invalid_filepath)
        if invalid_files:
            self.logger.info(
                "Invalid file(s) [%(file)s]: %(url)s",
                {"file": invalid_files, "url": self.pr_html_url},
            )
        return invalid_files

    def type_label(self) -> str:
        """Determine the type of the given pull request and return an appropriate
        label for it. Returns an empty string if the type is not programmed or the label
        already exists on the pull request.

        **documentation**: Contains a file with an extension from ``_DOCS_EXTENSIONS``

        **enhancement**: Some/all files were *modified*

        NOTE: These two types are mutually exclusive which means a modified docs file
        will be labeled **documentation** and not **enhancement**.
        """
        label = ""
        for file in self.pr_files:
            if file.path.suffix in self._DOCS_EXTENSIONS:
                if file.path.name != "DIRECTORY.md":
                    label = Label.DOCUMENTATION
                    break
            elif file.status == "modified":
                label = Label.ENHANCEMENT
        return label if label not in self.pr_labels else ""

    def files_to_check(self) -> List[File]:
        """Collect and return all the ``File`` which should be checked.

        Ignores:

        - Python test files
        - Dunder filenames like *__init__.py*
        - Files which were modified (Issue #11)
        - Files in the *scripts/* directory (Issue #11)
        """
        f = []
        for file in self.pr_files:
            filepath = file.path
            if (
                file.status != "modified"
                and filepath.suffix == ".py"
                and "scripts" not in filepath.parts
                and not filepath.name.startswith("__")
                and (
                    not (
                        filepath.name.startswith("test_")
                        or filepath.name.endswith("_test.py")
                    )
                )
            ):
                f.append(file)
        return f

    def _contains_testfile(self) -> bool:
        """Check whether any of the pull request files satisfy the naming convention
        for test discovery."""
        # https://docs.pytest.org/en/reorganize-docs/new-docs/user/naming_conventions.html
        for file in self.pr_files:
            if file.path.name.startswith("test_") or file.path.name.endswith(
                "_test.py"
            ):
                return True
        return False

    @staticmethod
    def _contains_testnode(module: ast.Module) -> bool:
        """Check whether the given module contains any function node or class node which
        satisfies the naming convention for test discorvery."""
        # https://docs.pytest.org/en/reorganize-docs/new-docs/user/naming_conventions.html
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                return True
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                return True
        return False

    def parse(self, file: File, source: Union[str, bytes]) -> None:
        """Parse the Python source code for tests, type hints and descriptive names."""
        try:
            module = ast.parse(source, filename=file.name)
        except SyntaxError as exc:
            import traceback

            msg = traceback.format_exc(limit=1)
            lineno = exc.lineno
            # Default the error comment to be posted on the first line of the file in
            # case it is ``None``
            if lineno is None:  # pragma: no cover
                lineno = 1
            self._pr_record.add_error(msg, file.name, lineno)
            self.logger.info(
                "Invalid Python code for the file: [%(file)s] %(url)s",
                {"file": file.name, "url": self.pr_html_url},
            )
            return None

        if not self._skip_doctest:
            # If the pull request does not contain any test file, then we will check
            # whether the file contains any test functions or classes as per the naming
            # convention.
            # We cannot assign the value we get from ``_contains_testnode`` to
            # ``self._contains_doctest`` as that will override the value for all files
            # present in the current pull request.
            visitor = PullRequestFileNodeVisitor(
                file, self._pr_record, self._contains_testnode(module)
            )
        else:
            visitor = PullRequestFileNodeVisitor(
                file, self._pr_record, self._skip_doctest
            )

        # We will only visit the top level nodes, rest will be taken care by the
        # node functions.
        visitor.generic_visit(module)

        # As this is going to be called for each file, we will represent the sequence
        # of labels as ``Set`` to avoid duplications.
        self._fill_labels()

    def collect_comments(self) -> List[Dict[str, Any]]:
        """A wrapper function to collect comments from the record instance."""
        return self._pr_record.collect_comments()

    def _fill_labels(self) -> None:
        """Fill the property ``add_labels`` and ``remove_labels`` with the appropriate
        labels as per the missing requirements and the current PR labels."""
        # Add or remove ``REQUIRE_TEST`` label
        if self._pr_record.doctest:
            if Label.REQUIRE_TEST not in self.pr_labels:
                self._add_labels.add(Label.REQUIRE_TEST)
        elif Label.REQUIRE_TEST in self.pr_labels:
            self._remove_labels.add(Label.REQUIRE_TEST)

        # Add or remove ``DESCRIPTIVE_NAMES`` label
        if self._pr_record.descriptive_name:
            if Label.DESCRIPTIVE_NAMES not in self.pr_labels:
                self._add_labels.add(Label.DESCRIPTIVE_NAMES)
        elif Label.DESCRIPTIVE_NAMES in self.pr_labels:
            self._remove_labels.add(Label.DESCRIPTIVE_NAMES)

        # Add or remove ``ANNOTATIONS`` label
        if self._pr_record.annotation or self._pr_record.return_annotation:
            if Label.ANNOTATIONS not in self.pr_labels:
                self._add_labels.add(Label.ANNOTATIONS)
        elif Label.ANNOTATIONS in self.pr_labels:
            self._remove_labels.add(Label.ANNOTATIONS)


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
        try:
            # There's no need to perform a ``generic_visit`` everytime a node function
            # is not present.
            visitor = getattr(self, method)
            visitor(node)
        except AttributeError:
            pass

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_AnyFunctionDef(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_AnyFunctionDef(node)

    def _visit_AnyFunctionDef(self, function: AnyFunctionT) -> None:
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
            self.record.add_descriptive_name(*nodedata)
        if function.name != "__init__" and not self._contains_doctest(function):
            self.record.add_doctest(*nodedata)
        if function.returns is None:
            self.record.add_return_annotation(*nodedata)
        self.generic_visit(function.args)

    def visit_arg(self, arg: ast.arg) -> None:
        """Visit the argument node. The argument can be positional-only, keyword-only or
        postitional/keyword.

        Rules:

        - Argument name should be of length > 1.
        - Argument should contain a valid annotation.
        """
        nodedata = self._nodedata(arg)
        if len(arg.arg) == 1:
            self.record.add_descriptive_name(*nodedata)
        if arg.arg != "self" and arg.annotation is None:
            self.record.add_annotation(*nodedata)

    def visit_ClassDef(self, klass: ast.ClassDef) -> None:
        """Visit the class node.

        Rules:

        - Class name should be of length > 1.
        - If a class contains doctest in the class-level docstring, doctest checking
          will be skipped for all its methods.
        """
        if len(klass.name) == 1:
            self.record.add_descriptive_name(*self._nodedata(klass))
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
            data = self.file.name, node.lineno, node.arg, "argument"
        return data
