import ast
from dataclasses import dataclass, field
from logging import Logger
from pathlib import PurePath
from typing import Any, Dict, List, Set, Tuple, Union

from algorithms_keeper.constants import Label
from algorithms_keeper.log import logger as main_logger
from algorithms_keeper.utils import File


def isdotfile(file: PurePath) -> bool:
    """Helper function to determine whether the given file is a dotfiles or not."""
    return file.name.startswith(".")


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
    def as_dict(self) -> Dict[str, Any]:
        """Helper function to represent a ``Comment`` instance in the ``dictionary``
        format. Useful for collecting all the comments into a list."""
        return {
            "body": self.body,
            "path": self.path,
            "line": self.line,
            "side": self.side,
        }


@dataclass(frozen=True)
class PullRequestRecord:

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
            f"Please provide return type hint for the {nodetype}: `{nodename}`.\n"
            f"**NOTE: If the {nodetype} returns `None`, please provide the type hint "
            f"as: `def function() -> None`"
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
        c = []
        for comments in self.__dict__.values():
            for comment in comments:
                c.append(comment.as_dict)
        return c


class PullRequestFilesParser:
    """A parser for all the pull request Python files."""

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

        # By providing the logger to the class, we won't have to log anything from the
        # pull requests module. Defaults to :attr:`algorithms_keeper.log.logger`
        self.logger = logger

        # Attribute to determine whether to skip doctest checking or not. This will
        # be set to `True` if the pull request contains a test file.
        self._skip_doctest = self._contains_testfile()

        # Attribute to store all the report data.
        self._pr_record = PullRequestRecord()

        # Initiate the label attributes. We are representing labels data in Set because
        # the parser will fill the data for each file and thus, there could be same
        # errors in multiple files resulting in the addition of the corresponding labels
        # multiple times.
        self._add_labels: Set[str] = set()
        self._remove_labels: Set[str] = set()

    @property
    def add_labels(self) -> List[str]:
        return list(self._add_labels)

    @property
    def remove_labels(self) -> List[str]:
        return list(self._remove_labels)

    @property
    def files_to_check(self) -> Tuple[File, ...]:
        """Collect and return all the files which should be checked.

        Ignores:
        - Python test files
        - Dunder filenames like `__init__.py`
        - Files which were modified (Issue #11)
        - Files in the `scripts/` directory (Issue #11)
        """
        if hasattr(self, "_files_to_check"):
            return self._files_to_check
        f = []
        for file in self.pr_files:
            filepath = file.path
            if (
                # TODO: Discuss this
                # file.status != "modified"
                filepath.suffix == ".py"
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
        # Cache for later use.
        self._files_to_check: Tuple[File, ...] = tuple(f)
        return self._files_to_check

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
                    elif not isdotfile(filepath):
                        invalid_filepath.append(file.name)
            elif filepath.suffix not in self._ACCEPTED_EXTENSIONS:
                invalid_filepath.append(file.name)
        invalid_files = ", ".join(invalid_filepath)
        if invalid_files:
            self.logger.info(
                "No extension file [%(file)s]: %(url)s",
                {"file": invalid_files, "url": self.pull_request["html_url"]},
            )
        return invalid_files

    def type_label(self) -> str:
        """Determine the type of the given pull request and return an appropriate
        label for it. Returns an empty string if the label already exists or the type is
        not programmed.

        "documentation": Contains a file with an extension from `_DOCS_EXTENSIONS`
        "enhancement": Some/all files were 'modified'

        NOTE: These two types are mutually exclusive which means a modified markdown
        file will be labeled "documentation" and not "enhancement".
        """
        label = ""
        if any(file.path.suffix in self._DOCS_EXTENSIONS for file in self.pr_files):
            label = Label.DOCUMENTATION
        if not label and any(file.status == "modified" for file in self.pr_files):
            label = Label.ENHANCEMENT
        if label in self.pr_labels:
            return ""
        return label

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
            self._pr_record.add_error(msg, file.name, exc.lineno)
            self.logger.info(
                "Invalid Python code for the file: [%(file)s] %(url)s",
                {"file": file.name, "url": self.pull_request["url"]},
            )
            return None

        if not self._skip_doctest:
            # If the pull request does not contain any test file, then we will check
            # whether the file contains any test functions or classes as per the naming
            # convention.
            # We cannot assign the value we get from `_contains_testnode` to
            # `self._contains_doctest` as that will override the value for all files
            # present in the current pull request.
            visitor = PullRequestFileNodeVisitor(
                file, self._pr_record, self._contains_testnode(module)
            )
        else:
            visitor = PullRequestFileNodeVisitor(
                file, self._pr_record, self._skip_doctest
            )

        for node in ast.walk(module):
            visitor.visit(node)

        # As this is going to be called for each file, we will represent the sequence
        # of labels as ``Set`` to avoid duplications.
        self._fill_labels()

    def collect_comments(self) -> List[Dict[str, Any]]:
        return self._pr_record.collect_comments()

    def _fill_labels(self) -> None:
        """Fill the property `add_labels` and `remove_labels` with the appropriate labels
        as per the missing requirements and the current PR labels."""
        # Add or remove REQUIRE_TEST label
        if self._pr_record.doctest:
            if Label.REQUIRE_TEST not in self.pr_labels:
                self._add_labels.add(Label.REQUIRE_TEST)
        elif Label.REQUIRE_TEST in self.pr_labels:
            self._remove_labels.add(Label.REQUIRE_TEST)

        # Add or remove DESCRIPTIVE_NAMES label
        if self._pr_record.descriptive_name:
            if Label.DESCRIPTIVE_NAMES not in self.pr_labels:
                self._add_labels.add(Label.DESCRIPTIVE_NAMES)
        elif Label.DESCRIPTIVE_NAMES in self.pr_labels:
            self._remove_labels.add(Label.DESCRIPTIVE_NAMES)

        # Add or remove ANNOTATIONS label
        if self._pr_record.annotation or self._pr_record.return_annotation:
            if Label.ANNOTATIONS not in self.pr_labels:
                self._add_labels.add(Label.ANNOTATIONS)
        elif Label.ANNOTATIONS in self.pr_labels:
            self._remove_labels.add(Label.ANNOTATIONS)


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
        self, file: File, record: PullRequestRecord, skip_doctest: bool
    ) -> None:
        self.record = record
        self.file = file
        self.skip_doctest = skip_doctest

    def visit(self, node: ast.AST) -> None:
        """Visit a node only if the `visit` function is defined."""
        method = "visit_" + node.__class__.__name__
        try:
            # We don't want to perform a `generic_visit`.
            # We will be walking down the abstract syntax tree and visit the nodes for
            # which the `visit_` function is defined. Now, first time we walk, we will
            # visit the `ast.Module` object whose function is not defined, thus
            # performing a `generic_visit` which will call all the child nodes which are
            # the top level function and class nodes and call the respective `visit_`
            # function. But, we are still walking and so after this cycle is over, we
            # will be calling the top level function and class nodes again. This will
            # add `MissingRequirementData` to the reporter multiple times.
            visitor = getattr(self, method)
            visitor(node)
        except AttributeError:
            pass

    def visit_FunctionDef(self, function: ast.FunctionDef) -> None:
        """Visit the function node.

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
        if not self.skip_doctest and function.name != "__init__":
            docstring = ast.get_docstring(function)
            if docstring is not None:
                for line in docstring.splitlines():
                    if line.strip().startswith(">>> "):
                        break
                else:
                    self.record.add_doctest(*nodedata)
            else:
                self.record.add_doctest(*nodedata)
        if function.returns is None:
            self.record.add_return_annotation(*nodedata)

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
        """
        if len(klass.name) == 1:
            self.record.add_descriptive_name(*self._nodedata(klass))

    def _nodedata(self, node: ast.AST) -> Tuple[str, int, str, str]:
        """Helper function to fill data required in the ``Comment`` object as per the
        given node."""
        if isinstance(node, ast.ClassDef):
            ret = self.file.name, node.lineno, node.name, "class"
        elif isinstance(node, ast.FunctionDef):
            ret = self.file.name, node.lineno, node.name, "function"
        elif isinstance(node, ast.arg):
            ret = self.file.name, node.lineno, node.arg, "argument"
        return ret
