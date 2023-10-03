import importlib
import inspect
import logging
from typing import Any, Iterable, Iterator, Mapping

from fixit import CstLintRule, LintConfig
from fixit.common.utils import LintRuleCollectionT
from fixit.rule_lint_engine import lint_file
from libcst import ParserSyntaxError

from algorithms_keeper.parser.files_parser import BaseFilesParser
from algorithms_keeper.parser.record import PullRequestReviewRecord
from algorithms_keeper.parser.rules import RequireDoctestRule
from algorithms_keeper.utils import File

RULES_DOTPATH: str = "algorithms_keeper.parser.rules"

DEFAULT_CONFIG: LintConfig = LintConfig(packages=[RULES_DOTPATH])

logger = logging.getLogger(__package__)


def get_rules_from_config(config: LintConfig = DEFAULT_CONFIG) -> LintRuleCollectionT:
    """Get rules from the packages specified in the lint config file, omitting
    block-listed rules.

    Custom rules should be imported in the ``__init__`` file  of the rules package
    along with all the rules used from ``fixit``. Also, make sure all the rule classes
    have the suffix `Rule`.
    """
    rules: LintRuleCollectionT = set()
    block_list_rules = config.block_list_rules
    for package in config.packages:
        pkg = importlib.import_module(package)
        for name in dir(pkg):
            if name.endswith("Rule"):
                obj = getattr(pkg, name)
                if (
                    obj is not CstLintRule
                    and issubclass(obj, CstLintRule)
                    and not inspect.isabstract(obj)
                    and name not in block_list_rules
                ):
                    rules.add(obj)
    return rules


class PythonParser(BaseFilesParser):
    """Parser for all the Python files in the pull request.

    This object performs no I/O of its own as the logic needs to be separated. This
    means that the function instantiating the object needs to provide the source code
    of the file to be parsed. For this, there's a helper function ``files_to_check``
    to generate the list of all the valid Python files in the provided pull request. The
    user function will request the file content from GitHub and pass it to the main
    function ``parse``.
    """

    _pr_report: PullRequestReviewRecord
    _rules: LintRuleCollectionT

    DOCS_EXTENSIONS: tuple[str, ...] = (".md", ".rst")

    ACCEPTED_EXTENSIONS: tuple[str, ...] = (
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
        *DOCS_EXTENSIONS,
    )

    def __init__(
        self,
        pr_files: Iterable[File],
        pull_request: Mapping[str, Any],
    ) -> None:
        super().__init__(pr_files, pull_request)
        self._pr_record = PullRequestReviewRecord()
        # Collection of rules are going to be static for a pull request, so let's
        # extract it out and store it.
        self._rules = get_rules_from_config()
        # If the pull request contains a test file as per the naming convention, there's
        # no need to run ``RequireDoctestRule``.
        if self._contains_testfile():
            self._rules.discard(RequireDoctestRule)

    @property
    def labels_to_add(self) -> list[str]:
        return self._pr_record.labels_to_add

    @property
    def labels_to_remove(self) -> list[str]:
        return self._pr_record.labels_to_remove

    def collect_comments(self) -> list[dict[str, Any]]:
        return self._pr_record.collect_comments()

    def collect_review_contents(self) -> list[str]:
        return self._pr_record.collect_review_contents()

    def files_to_check(self, ignore_modified: bool) -> Iterator[File]:
        """Generate all the ``File`` which should be checked.

        The caller of this function should use a loop to generate and parse the files
        one at a time. This way the labels will be filled only after all the files
        have been parsed.

        Ignores:

        - Python test files
        - Dunder filenames like *__init__.py*
        - Optionally ignore files which were modified (Issue #11)
        - Files in the *scripts/* directory (Issue #11)
        """
        for file in self.pr_files:
            filepath = file.path
            if (
                # If *ignore_modified* is ``True``, yield only the added files,
                # otherwise yield all the files.
                (not ignore_modified or file.status == "added")
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

    def parse(self, file: File, source: bytes) -> None:
        """Run the lint engine on the given *source* for the *file*."""
        try:
            reports = lint_file(
                file.path,
                source,
                use_ignore_byte_markers=False,
                use_ignore_comments=False,
                config=DEFAULT_CONFIG,
                rules=self._rules,
            )
            self._pr_record.add_comments(reports, file.name)
        except (SyntaxError, ParserSyntaxError) as exc:
            self._pr_record.add_error(exc, file.name)
            logger.info(
                "Invalid Python code for the file: [%s] %s", file.name, self.pr_html_url
            )

    def _contains_testfile(self) -> bool:
        """Check whether any of the pull request files satisfy the naming convention
        for test discovery."""
        # https://docs.pytest.org/en/reorganize-docs/new-docs/user/naming_conventions.html
        for file in self.pr_files:
            filepath = file.path
            if filepath.suffix == ".py" and (
                filepath.name.startswith("test_") or filepath.name.endswith("_test.py")
            ):
                return True
        return False
