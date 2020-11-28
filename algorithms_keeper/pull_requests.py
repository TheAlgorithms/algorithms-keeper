"""Pull request module.

Copy and paste to http://www.webgraphviz.com/ to look at the stages of a pull request.

digraph "PR stages" {
  /*
  Box represents labels
  Require labels include
  - `require tests`
  - `require type hints`
  - `require descriptive names`
  */
  "New PR" [color=yellow]
  "Awaiting review" [shape=box, color=green]
  "Awaiting changes" [shape=box, color=blue]
  "Require labels" [shape=box, color=orange]
  "Tests are failing" [shape=box, color=red]
  "Approved" [color=yellow]

  "New PR" -> "Awaiting review" [label="PR opened\nAssume PR is perfect", color=green]
  "Awaiting review" -> "Awaiting changes" [label="Review requests changes", color=red]
  "Awaiting changes" -> "Awaiting review" [label="Author made changes", color=orange]

  "Awaiting review" -> "Approved" [label="Review approves", color=green]
  "Awaiting changes" -> "Approved" [label="Review approves", color=green]

  "Awaiting review" -> "Tests are failing" [label="Tests failed", color=red]
  "Tests are failing" -> "Awaiting review" [label="Tests passed", color=green]

  "Awaiting review" -> "Require labels" [label="Requirements not satisfied", color=red]
  "Require labels" -> "Awaiting review" [label="Requirements satisfied", color=green]
}
"""
import re
from typing import Any

from gidgethub import routing
from gidgethub.aiohttp import GitHubAPI
from gidgethub.sansio import Event

from . import utils
from .constants import (
    CHECKBOX_NOT_TICKED_COMMENT,
    EMPTY_BODY_COMMENT,
    MAX_PR_REACHED_COMMENT,
    NO_EXTENSION_COMMENT,
    PR_NOT_READY_LABELS,
    PR_REPORT_COMMENT,
    Label,
)
from .log import logger
from .parser import PullRequestFilesParser

MAX_PR_PER_USER = 1

router = routing.Router()


@router.register("pull_request", action="opened")
async def close_invalid_or_additional_pr(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Close an invalid pull request or close additional pull requests made by the
    user and dismiss all the review requests from it.

    A pull request is considered invalid if:
    - It doesn't contain any description
    - The user has not ticked any of the checkboxes in the pull request template
    - The file extension is invalid (Extensionless files) [This will be checked in
      `check_pr_files` function]

    A user will be allowed a fix number of pull requests at a time which will be
    indicated by the `MAX_PR_BY_USER` constant. This is done so as to avoid spam PRs.
    To disable the limit -> `MAX_PR_BY_USER` = 0

    These checks won't be done for the pull request made by a member or owner of the
    organization.
    """
    installation_id = event.data["installation"]["id"]
    pull_request = event.data["pull_request"]
    author_association = pull_request["author_association"].lower()

    if author_association not in {"owner", "member"}:
        pr_body = pull_request["body"]
        pr_author = pull_request["user"]["login"]
        comment = None

        if not pr_body:
            comment = EMPTY_BODY_COMMENT.format(user_login=pr_author)
            logger.info("Empty PR body: %(url)s", {"url": pull_request["html_url"]})
        elif re.search(r"\[x]", pr_body, re.IGNORECASE) is None:
            comment = CHECKBOX_NOT_TICKED_COMMENT.format(user_login=pr_author)
            logger.info("Empty checklist: %(url)s", {"url": pull_request["html_url"]})

        if comment is not None:
            await utils.close_pr_or_issue(
                gh,
                installation_id,
                comment=comment,
                pr_or_issue=pull_request,
                label=Label.INVALID,
            )
            return None
        elif MAX_PR_PER_USER > 0:
            user_pr_numbers = await utils.get_user_open_pr_numbers(
                gh,
                installation_id,
                repository=event.data["repository"]["full_name"],
                user_login=pr_author,
            )

            if len(user_pr_numbers) > MAX_PR_PER_USER:
                logger.info(
                    "Multiple open PRs: %(url)s", {"url": pull_request["html_url"]}
                )
                # Convert list of numbers to: "#1, #2, #3"
                pr_number = "#{}".format(", #".join(map(str, user_pr_numbers)))
                await utils.close_pr_or_issue(
                    gh,
                    installation_id,
                    comment=MAX_PR_REACHED_COMMENT.format(
                        user_login=pr_author, pr_number=pr_number
                    ),
                    pr_or_issue=pull_request,
                )
                return None

    if not pull_request["draft"]:
        # Assume that the pull request is perfect and ready for review, then when any
        # `require_` labels or `failed_test` label is added, we will remove this label.
        # This label will be added back when all those labels are removed.
        await utils.add_label_to_pr_or_issue(
            gh, installation_id, pr_or_issue=pull_request, label=Label.AWAITING_REVIEW
        )

        # We will check files only if the pull request is valid and thus, not closed.
        await check_pr_files(event, gh, *args, **kwargs)


@router.register("pull_request", action="reopened")
@router.register("pull_request", action="ready_for_review")
@router.register("pull_request", action="synchronize")
async def check_pr_files(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Check all the pull request files for extension, type hints, tests and
    class, function and parameter names.

    This function will accomplish the following tasks:
    - Check for file extension and close the pull request if a file do not contain any
      extension. Ignores all non-python files and any file in `.github` directory.
    - Check for type hints, tests and descriptive names in the submitted files and
      label it appropriately. Sends the report if there are any errors only when the
      pull request is opened.

    When a pull request is opened, this function will be triggered only if there the
    pull request is considered valid. This function will also be triggered when a
    pull request is made ready for review, a new commit has been pushed to the
    pull request and when the pull request is reopened.
    """
    installation_id = event.data["installation"]["id"]
    pull_request = event.data["pull_request"]

    if pull_request["draft"]:
        return None

    pr_labels = [label["name"] for label in pull_request["labels"]]
    pr_author = pull_request["user"]["login"]
    pr_files = await utils.get_pr_files(gh, installation_id, pull_request=pull_request)
    parser = PullRequestFilesParser()
    files_to_check = []

    # We will collect all the files first as there is this one problem case:
    # A pull request with two files: `main.py` and `test_main.py`
    # If in this loop, the main file came first, we will check for `doctest` even though
    # there is a separate test file. We cannot hope that the test file comes first in
    # the loop.
    for file in pr_files:
        filepath = file.path
        if not filepath.suffix and ".github" not in filepath.parts:
            logger.info(
                "No extension file [%(file)s]: %(url)s",
                {"file": file.name, "url": pull_request["html_url"]},
            )
            await utils.close_pr_or_issue(
                gh,
                installation_id,
                comment=NO_EXTENSION_COMMENT.format(user_login=pr_author),
                pr_or_issue=pull_request,
                label=Label.INVALID,
            )
            return None
        elif filepath.suffix != ".py" or filepath.name.startswith("__"):
            continue
        # If there is a test file then we do not want to check for `doctest`.
        # NOTE: This should come after the check for `.py` files.
        elif filepath.name.startswith("test_") or filepath.name.endswith("_test.py"):
            parser.skip_doctest = True
            continue
        files_to_check.append(file)

    for file in files_to_check:
        code = await utils.get_file_content(gh, installation_id, file=file)
        parser.parse_code(file.name, code)

    labels_to_add, labels_to_remove = parser.labels_to_add_and_remove(pr_labels)

    if labels_to_add:
        await utils.add_label_to_pr_or_issue(
            gh, installation_id, label=labels_to_add, pr_or_issue=pull_request
        )

    if labels_to_remove:
        await utils.remove_label_from_pr_or_issue(
            gh, installation_id, label=labels_to_remove, pr_or_issue=pull_request
        )

    # No need to comment on every commit pushed to the pull request.
    if event.data["action"] == "synchronize":
        return None

    report_content = parser.create_report_content()
    if report_content:
        logger.info(
            "Missing requirements in parsed files [%(file)s]: %(url)s",
            {
                "file": ", ".join([file.name for file in files_to_check]),
                "url": pull_request["html_url"],
            },
        )
        await utils.add_comment_to_pr_or_issue(
            gh,
            installation_id,
            comment=PR_REPORT_COMMENT.format(
                content=report_content, user_login=pr_author
            ),
            pr_or_issue=pull_request,
        )


@router.register("pull_request", action="ready_for_review")
async def check_ci_ready_for_review_pr(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Check test status on the latest commit and add or remove label when a pull
    request is made ready for review.

    When a PR is made ready for review, the checks do not start automatically,
    thus the check run completed event is not triggered and no labels are added or
    removed if the checks are passing or failing. Thus, we need to manually check it
    with respect to the latest commit on head.
    """
    from . import check_runs

    await check_runs.check_ci_status_and_label(event, gh, *args, **kwargs)


@router.register("pull_request_review", action="submitted")
async def update_pr_label_for_review(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Update the label for a pull request according to the review submitted. Only
    the reviews submitted by either the member or owner will count.

    - Ignore all the comments.
    - Add label when a maintainer request any changes.
    - Remove the label, if present, when a maintainer approves.

    Label: `Label.CHANGES_REQUESTED`
    """
    installation_id = event.data["installation"]["id"]
    pull_request = event.data["pull_request"]
    review = event.data["review"]
    review_state = review["state"]

    if review_state == "commented":
        return None

    author_association = review["author_association"].lower()
    if author_association in {"member", "owner"}:
        pr_labels = [label["name"] for label in pull_request["labels"]]
        if review_state == "changes_requested":
            if Label.CHANGES_REQUESTED not in pr_labels:
                await utils.add_label_to_pr_or_issue(
                    gh,
                    installation_id,
                    label=Label.CHANGES_REQUESTED,
                    pr_or_issue=pull_request,
                )
        elif review_state == "approved":
            if Label.CHANGES_REQUESTED in pr_labels:
                await utils.remove_label_from_pr_or_issue(
                    gh,
                    installation_id,
                    label=Label.CHANGES_REQUESTED,
                    pr_or_issue=pull_request,
                )
            # If a pull request is directly approved without asking for any changes,
            # remove the `awaiting reviews` label as well if present. (Issue #10)
            elif Label.AWAITING_REVIEW in pr_labels:
                await utils.remove_label_from_pr_or_issue(
                    gh,
                    installation_id,
                    label=Label.AWAITING_REVIEW,
                    pr_or_issue=pull_request,
                )


@router.register("pull_request", action="labeled")
@router.register("pull_request", action="unlabeled")
async def pr_awaiting_review_label(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Add/remove the label which indicates that the pull request is ready to be
    reviewed according to the label and unlabel events if the pull request has not
    already been reviewed.

    This assumes that the label was added when the pull request was opened to cover
    the case where the bot detected no errors in the pull request, thus no `require_`
    or `failed_test` labels were added.

    To know whether the pull request has already been reviewed, we will check whether
    `Label.CHANGES_REQUESTED` exist or not.

    Label: `Label.AWAITING_REVIEW`
    """
    installation_id = event.data["installation"]["id"]
    pull_request = event.data["pull_request"]
    # The label which was added or removed.
    label = event.data["label"]["name"]
    pr_labels = [label["name"] for label in pull_request["labels"]]

    if event.data["action"] == "labeled":
        if label in PR_NOT_READY_LABELS or label == Label.CHANGES_REQUESTED:
            if Label.AWAITING_REVIEW in pr_labels:
                await utils.remove_label_from_pr_or_issue(
                    gh,
                    installation_id,
                    pr_or_issue=pull_request,
                    label=Label.AWAITING_REVIEW,
                )
    else:
        # These labels are removed only when a PR is approved, so we don't want to add
        # the `awaiting_review` label back again. (Issue #10)
        if label == Label.CHANGES_REQUESTED or label == Label.AWAITING_REVIEW:
            return None
        # Add label only if none of the PR_NOT_READY_LABELS are present in `pr_labels`.
        if all(label not in pr_labels for label in PR_NOT_READY_LABELS):
            # Don't add the label if the pr is already reviewed.
            if (
                Label.AWAITING_REVIEW not in pr_labels
                and Label.CHANGES_REQUESTED not in pr_labels
            ):
                await utils.add_label_to_pr_or_issue(
                    gh,
                    installation_id,
                    pr_or_issue=pull_request,
                    label=Label.AWAITING_REVIEW,
                )


@router.register("pull_request", action="synchronize")
async def add_review_label_on_changes(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Add the `awaiting review` label once the author made the requested changes.

    NOTE: This will change the label on the first commit after a change has been
    requested, the author might not be ready by then.
    """
    installation_id = event.data["installation"]["id"]
    pull_request = event.data["pull_request"]
    pr_labels = [label["name"] for label in pull_request["labels"]]

    if Label.CHANGES_REQUESTED in pr_labels:
        await utils.remove_label_from_pr_or_issue(
            gh,
            installation_id,
            label=Label.CHANGES_REQUESTED,
            pr_or_issue=pull_request,
        )
        await utils.add_label_to_pr_or_issue(
            gh,
            installation_id,
            label=Label.AWAITING_REVIEW,
            pr_or_issue=pull_request,
        )
