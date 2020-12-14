from logging import Logger
from typing import Any, Dict, Generator, List

from fixit import LintConfig
from fixit.common.utils import LintRuleCollectionT, import_distinct_rules_from_package
from fixit.rule_lint_engine import lint_file
from libcst import ParserSyntaxError

from algorithms_keeper.log import logger as main_logger
from algorithms_keeper.parser.files_parser import PythonFilesParser
from algorithms_keeper.parser.record import PullRequestReviewRecord
from algorithms_keeper.utils import File

RULES_DOTPATH: str = "algorithms_keeper.parser.rules"

REQUIRE_DOCTEST_RULE: str = "RequireDoctestRule"


class PythonParser(PythonFilesParser):
    """Parser for all the Python files in the pull request.

    This object performs no I/O of its own as the logic needs to be separated. This
    means that the function instantiating the object needs to provide the source code
    of the file to be parsed. For this, there's a helper function ``files_to_check``
    to generate the list of all the valid Python files in the provided pull request. The
    user function will request the file content from GitHub and pass it to the main
    function ``parse``.
    """

    _config: LintConfig
    _pr_report: PullRequestReviewRecord
    _rules: LintRuleCollectionT

    def __init__(
        self,
        pr_files: List[File],
        pull_request: Dict[str, Any],
        logger: Logger = main_logger,
    ) -> None:
        super().__init__(pr_files, pull_request, logger)
        # If the pull request contains a test file as per the naming convention, there's
        # no need to run ``RequireDoctestRule``.
        config = LintConfig(packages=[RULES_DOTPATH])
        if self._contains_testfile():
            config.block_list_rules.append(REQUIRE_DOCTEST_RULE)
        self._config = config
        self._pr_record = PullRequestReviewRecord()
        # Collection of rules are going to be static for a pull request, so let's
        # extract it out and store it. This should be set after the check for testfile.
        self._rules = self.get_rules_from_config()

    @property
    def labels_to_add(self) -> List[str]:
        return self._pr_record.labels_to_add

    @property
    def labels_to_remove(self) -> List[str]:
        return self._pr_record.labels_to_remove

    def collect_comments(self) -> List[Dict[str, Any]]:
        return self._pr_record.collect_comments()

    def files_to_check(self, ignore_modified: bool) -> Generator[File, None, None]:
        """Generate all the ``File`` which should be checked.

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

    def parse(self, file: File, source: bytes) -> None:
        """Run the lint engine on the given *source* for the *file*."""
        try:
            reports = lint_file(
                file.path,
                source,
                use_ignore_byte_markers=False,
                use_ignore_comments=False,
                config=self._config,
                rules=self._rules,
            )
            self._pr_record.add_comments(reports, file.name)
        except (SyntaxError, ParserSyntaxError) as exc:
            import traceback

            msg: str = traceback.format_exc(limit=1)
            # It seems that ``ParserSyntaxError`` is not a subclass of ``SyntaxError``,
            # the same information is stored under a different attribute.
            # Using ``try ... except AttributeError: ...`` makes ``mypy`` mad.
            if isinstance(exc, SyntaxError):
                lineno = exc.lineno
            else:
                lineno = exc.raw_line
            self._pr_record.add_error(msg, file.name, lineno)
            self.logger.info(
                "Invalid Python code for the file: [%(file)s] %(url)s",
                {"file": file.name, "url": self.pr_html_url},
            )

    def get_rules_from_config(self) -> LintRuleCollectionT:
        """Get rules from the packages specified in the lint config file, omitting
        block-listed rules.

        This function is directly taken from
        ``fixit.common.config.get_rules_from_config`` with the modification being the
        custom configuration.
        """
        lint_config = self._config
        rules: LintRuleCollectionT = set()
        for package in lint_config.packages:
            rules_from_pkg = import_distinct_rules_from_package(
                package, lint_config.block_list_rules
            )
            rules.update(rules_from_pkg)
        return rules

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
