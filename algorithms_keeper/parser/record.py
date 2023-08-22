from dataclasses import asdict, dataclass, field
from typing import Any, Collection, Union

from fixit.common.report import BaseLintRuleReport
from libcst import ParserSyntaxError

from algorithms_keeper.constants import Label

# Mapping of rule to the appropriate label.
RULE_TO_LABEL: dict[str, str] = {
    "RequireDescriptiveNameRule": Label.DESCRIPTIVE_NAME,
    "RequireDoctestRule": Label.REQUIRE_TEST,
    "RequireTypeHintRule": Label.TYPE_HINT,
}

MULTIPLE_COMMENT_SEPARATOR: str = "\n\n"


@dataclass(frozen=False)
class ReviewComment:
    # Text of the review comment. This is different from the body of the review itself.
    body: str

    # The relative path to the file that necessitates a review comment.
    path: str

    # The line of the blob in the pull request diff that the comment applies to.
    line: int

    # In a split diff view, the side of the diff that the pull request's changes appear
    # on. As we can only comment on a line present in the pull request diff, we default
    # to the RIGHT side.
    #
    # From GitHub:
    # Can be LEFT or RIGHT. Use LEFT for deletions that appear in red. Use RIGHT for
    # additions that appear in green or unchanged lines that appear in white and are
    # shown for context.
    side: str = field(init=False, default="RIGHT")


@dataclass(frozen=False)
class PullRequestReviewRecord:
    """A Record object to store the necessary information regarding the current pull
    request. This should only be initialized once per pull request and use its public
    interface to add and get the appropriate data.
    """

    # Initialize the label attributes. These should be filled with the appropriate
    # labels **only** after all the files have been linted.
    labels_to_add: list[str] = field(default_factory=list, init=False)
    labels_to_remove: list[str] = field(default_factory=list, init=False)

    # Store all the ``ReviewComment`` instances.
    _comments: list[ReviewComment] = field(default_factory=list, init=False, repr=False)

    # A set of rules which were violated during the runtime of the parser for the
    # current pull request. This is being represented as ``set`` internally to avoid
    # duplication.
    _violated_rules: set[str] = field(default_factory=set, init=False, repr=False)

    def add_comments(
        self, reports: Collection[BaseLintRuleReport], filepath: str
    ) -> None:
        """Construct and add comments from the reports.

        If the line on which the comment is to be posted already exists, then the
        *body* is simply added to the respective comment's body provided it is in the
        same file. This is done to avoid adding multiple comments on the same line.
        """
        for report in reports:
            self._violated_rules.add(report.code)
            if self._lineno_exist(report.message, filepath, report.line):
                continue
            self._comments.append(ReviewComment(report.message, filepath, report.line))

    def add_error(
        self, exc: Union[SyntaxError, ParserSyntaxError], filepath: str
    ) -> None:
        """Add any exception faced while parsing the source code."""
        import traceback

        message = traceback.format_exc(limit=1)
        # It seems that ``ParserSyntaxError`` is not a subclass of ``SyntaxError``,
        # the same information is stored under a different attribute. There is no
        # filename information in ``ParserSyntaxError``, thus the parameter `filepath`.
        if isinstance(exc, SyntaxError):  # noqa: SIM108, pragma: no cover
            lineno = exc.lineno or 1
        else:
            lineno = exc.raw_line
        body = (
            f"An error occurred while parsing the file: `{filepath}`\n"
            f"```python\n{message}\n```"
        )
        self._comments.append(ReviewComment(body, filepath, lineno))

    def fill_labels(self, current_labels: Collection[str]) -> None:
        """Fill the ``add_labels`` and ``remove_labels`` with the appropriate data.

        This method is **only** to be called once after all the files have been parsed.

        *current_labels* is a collection of labels present on the pull request.
        """
        for rule, label in RULE_TO_LABEL.items():
            if rule in self._violated_rules:
                if label not in current_labels and label not in self.labels_to_add:
                    self.labels_to_add.append(label)
            elif label in current_labels and label not in self.labels_to_remove:
                self.labels_to_remove.append(label)

    def collect_comments(self) -> list[dict[str, Any]]:
        """Return all the review comments in the record instance.

        This is how GitHub wants the *comments* value while creating the review.
        """
        return [asdict(comment) for comment in self._comments]

    def collect_review_contents(self) -> list[str]:
        """Collect all the review comments as list of strings.

        If the comment body contains multiple comments from rules being violated
        multiple time, each comment will be replaced in a way to maintain consistency
        in the following format.

        The format will be: ``filepath:lineno: message``
        """
        content = []
        for comment in self._comments:
            if MULTIPLE_COMMENT_SEPARATOR in comment.body:
                comment.body = comment.body.replace(
                    MULTIPLE_COMMENT_SEPARATOR,
                    f"{MULTIPLE_COMMENT_SEPARATOR}**{comment.path}:{comment.line}:** ",
                )
            content.append(f"**{comment.path}:{comment.line}:** {comment.body}")
        return content

    def _lineno_exist(self, body: str, filepath: str, lineno: int) -> bool:
        """Determine whether any review comment is registered for the given *lineno*
        for the given *filepath*.

        If ``True``, add the provided *body* to the respective comment body. This helps
        in avoiding multiple review comments on the same line.
        """
        for comment in self._comments:
            if comment.line == lineno and comment.path == filepath:
                comment.body += f"{MULTIPLE_COMMENT_SEPARATOR}{body}"
                return True
        return False
