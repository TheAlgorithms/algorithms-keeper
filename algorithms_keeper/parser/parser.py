import ast
from logging import Logger
from typing import Any, Dict, Generator, List, Tuple, Union

from algorithms_keeper.constants import Label
from algorithms_keeper.log import logger as main_logger
from algorithms_keeper.parser.record import PullRequestReviewRecord
from algorithms_keeper.parser.visitor import PullRequestFileNodeVisitor
from algorithms_keeper.utils import File


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

    pr_author: str
    pr_labels: List[str]
    pr_html_url: str

    DOCS_EXTENSIONS: Tuple[str, ...] = (".md", ".rst")

    ACCEPTED_EXTENSIONS: Tuple[str, ...] = (
        # Configuration files
        ".ini",
        ".toml",
        ".yaml",
        ".yml",
        ".cfg",
        # Data files
        ".csv",
        ".json",
        ".txt",
        # Good old Python file
        ".py",
    ) + DOCS_EXTENSIONS

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

    @property
    def add_labels(self) -> List[str]:
        return self._pr_record.add_labels

    @property
    def remove_labels(self) -> List[str]:
        return self._pr_record.remove_labels

    def collect_comments(self) -> List[Dict[str, Any]]:
        """A wrapper function to collect comments from the record instance."""
        return self._pr_record.collect_comments()

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
            elif filepath.suffix not in self.ACCEPTED_EXTENSIONS:
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
            if file.path.suffix in self.DOCS_EXTENSIONS:
                if file.path.name != "DIRECTORY.md":
                    label = Label.DOCUMENTATION
                    break
            elif file.status == "modified":
                label = Label.ENHANCEMENT
        return label if label not in self.pr_labels else ""

    def files_to_check(self, ignore_modified: bool) -> Generator[File, None, None]:
        """Collect and return all the ``File`` which should be checked.

        Ignores:

        - Python test files
        - Dunder filenames like *__init__.py*
        - Optionally ignore files which were modified (Issue #11)
        - Files in the *scripts/* directory (Issue #11)
        """
        ignore = "modified" if ignore_modified else None
        for file in self.pr_files:
            filepath = file.path
            if (
                file.status != ignore
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
                yield file
        # Fill the labels **only** after all the files have been parsed.
        self._pr_record.fill_labels(self.pr_labels)

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
        visitor.visit(module)
