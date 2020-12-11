from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Set

from algorithms_keeper.constants import Label, Missing

# Mapping of missing requirement to the appropriate label.
# ``Missing.RETURN_TYPE_HINT`` and ``Missing.TYPE_HINT`` corresponds to the same label.
REQUIREMENT_TO_LABEL = {
    Missing.DOCTEST: Label.REQUIRE_TEST,
    Missing.TYPE_HINT: Label.TYPE_HINT,
    Missing.DESCRIPTIVE_NAME: Label.DESCRIPTIVE_NAME,
}


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

    # Store all the labels to be added and removed.
    add_labels: List[str] = field(default_factory=list)
    remove_labels: List[str] = field(default_factory=list)

    # Store all the ``ReviewComment`` instances.
    _comments: List[ReviewComment] = field(default_factory=list)

    # Store any of the error faced while parsing the source code.
    _error: List[ReviewComment] = field(default_factory=list)

    # Missing requirements type in string. This is represented as ``set`` internally so
    # as to avoid duplication.
    _requirement_registered: Set[str] = field(default_factory=set)

    def add_comment(
        self,
        filepath: str,
        lineno: int,
        nodename: str,
        nodetype: str,
        missing_requirement: str,
    ) -> None:
        """Add a comment and register the *missing_requirement*.

        If the line on which the comment is to be posted already exists, then the
        *body* is simply added to the respective comment's body provided it is in the
        same file. This is done to avoid adding multiple comments on the same line.

        :param filepath: Path from the repository root to the file
        :param lineno: Line number in the file
        :param nodename: Name of the class/function/parameter
        :param nodetype: Type of nodename as in class/function/parameter
        :param missing_requirement: Type of the requirement missing
        ``algorithms_keeper.constants.Missing``
        """
        body = f"Please provide {missing_requirement} for the {nodetype}: `{nodename}`"
        if missing_requirement == Missing.RETURN_TYPE_HINT:
            body += (
                f". **If the {nodetype} does not return a value, please provide "
                f"the type hint as:** `def function() -> None:`"
            )
            # Return type hint and type hint corresponds to the same label.
            missing_requirement = Missing.TYPE_HINT
        self._requirement_registered.add(missing_requirement)
        if self._lineno_exist(lineno, filepath, body):
            return None
        self._comments.append(ReviewComment(body, filepath, lineno))

    def add_error(self, message: str, filepath: str, lineno: int) -> None:
        """Add any exceptions faced while parsing the source code in the parser.

        The parameter *message* is the traceback text with limit=1, no need for the
        full traceback.
        """
        body = (
            f"An error occured while parsing the file: `{filepath}`\n"
            f"```python\n{message}\n```"
        )
        self._error.append(ReviewComment(body, filepath, lineno))

    def fill_labels(self, current_labels: List[str]) -> None:
        """Fill the ``add_labels`` and ``remove_labels`` with the appropriate data.

        This method is **only** to be called once after all the files have been parsed.

        *current_labels* is a list of labels present on the pull request.
        """
        for requirement, label in REQUIREMENT_TO_LABEL.items():
            if requirement in self._requirement_registered:
                if label not in current_labels and label not in self.add_labels:
                    self.add_labels.append(label)
            elif label in current_labels and label not in self.remove_labels:
                self.remove_labels.append(label)

    def collect_comments(self) -> List[Dict[str, Any]]:
        """Return all the review comments in the record instance.

        This is how GitHub wants the *comments* value while creating the review.
        """
        return [asdict(comment) for comment in self._comments]

    def _lineno_exist(self, lineno: int, filepath: str, body: str) -> bool:
        """Determine whether any review comment is registered for the given *lineno*
        for the given *filepath*.

        If ``True``, add the provided *body* to the respective comment body. This helps
        in avoiding multiple review comments on the same line.
        """
        for comment in self._comments:
            if comment.line == lineno and comment.path == filepath:
                comment.body += f"\n\n{body}"
                return True
        return False
