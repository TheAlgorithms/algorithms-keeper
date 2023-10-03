"""Pull request module.

Copy and paste to http://www.webgraphviz.com/ to look at the stages of a pull request.

digraph "PR stages" {
  /*
  Box represents labels
  */
  "New PR" [color=yellow]
  "Awaiting review" [shape=box, color=green]
  "Awaiting changes" [shape=box, color=blue]
  "Approved" [color=yellow]

  "New PR" -> "Awaiting review" [label="PR opened", color=green]
  "Awaiting review" -> "Awaiting changes" [label="Review requests changes", color=red]
  "Awaiting changes" -> "Awaiting review" [label="Author made changes", color=orange]

  "Awaiting review" -> "Approved" [label="Review approves", color=green]
  "Awaiting changes" -> "Approved" [label="Review approves", color=green]
}
"""
import asyncio
import logging
import re
from typing import Any, Optional

from gidgethub import routing
from gidgethub.sansio import Event

from algorithms_keeper import utils
from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.constants import (
    CHECKBOX_NOT_TICKED_COMMENT,
    EMPTY_PR_BODY_COMMENT,
    INVALID_EXTENSION_COMMENT,
    MAX_PR_REACHED_COMMENT,
    PR_REVIEW_COMMENT,
    Label,
)
from algorithms_keeper.parser import PythonParser

# To disable this check, set the constant to 0.
MAX_PR_PER_USER = 3
STAGE_PREFIX = "awaiting"
MAX_RETRIES = 5

pull_request_router = routing.Router()

logger = logging.getLogger(__package__)


async def update_stage_label(
    gh: GitHubAPI, *, pull_request: dict[str, Any], next_label: Optional[str] = None
) -> None:
    """Update the stage label of the given pull request.

    This is a two steps process with one being optional:

    1. Remove any of the stage labels, if present.
    2. Add the next stage label given in the `next_label` argument.

    If `next_label` argument is not provided, then only the first step is performed.
    """
    for label in pull_request["labels"]:
        # The bot should be smart enough to figure out that if the next_label
        # already exist, then there's no need to change the pull request stage.
        label_name = label["name"]
        if label_name == next_label:
            return None
        elif STAGE_PREFIX in label_name:
            await utils.remove_label_from_pr_or_issue(
                gh, label=label_name, pr_or_issue=pull_request
            )
    if next_label is not None:
        await utils.add_label_to_pr_or_issue(
            gh, label=next_label, pr_or_issue=pull_request
        )


@pull_request_router.register("pull_request", action="opened")
@pull_request_router.register("pull_request", action="ready_for_review")
async def add_review_label_on_pr_opened(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Add the awaiting reviews label when a pull request is opened.

    Assume that the pull request is perfect and ready for review, then when any
    `require_` labels or `failed_test` label is added, this label will be removed.
    The label will be added back when all those labels are removed.
    """
    pull_request = event.data["pull_request"]
    if not pull_request["draft"]:
        await update_stage_label(gh, pull_request=pull_request, next_label=Label.REVIEW)


@pull_request_router.register("pull_request", action="opened")
async def close_invalid_or_additional_pr(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Close an invalid pull request or close additional pull requests made by the
    user and dismiss all the review requests from it.

    A pull request is considered invalid if:

    - It doesn't contain any description
    - The user has not ticked any of the checkboxes in the pull request template
    - The file extension is invalid (Extensionless files) [This will be checked in
      ``check_pr_files`` function]

    A user will be allowed a fix number of pull requests at a time which will be
    indicated by the ``MAX_PR_BY_USER`` constant. This is done so as to avoid spam PRs.
    To disable the limit: ``MAX_PR_BY_USER = 0``

    These checks won't be done for the pull request made by a member or owner of the
    organization.
    """
    pull_request = event.data["pull_request"]

    if (
        pull_request["author_association"].lower() not in {"owner", "member"}
        # Don't check for invalid pull request made by a bot.
        and pull_request["user"]["type"].lower() != "bot"
    ):
        pr_body = pull_request["body"]
        pr_author = pull_request["user"]["login"]
        comment = None

        if not pr_body:
            comment = EMPTY_PR_BODY_COMMENT.format(user_login=pr_author)
            logger.info("Empty PR body: %s", pull_request["html_url"])
        elif re.search(r"\[x]", pr_body, re.IGNORECASE) is None:
            comment = CHECKBOX_NOT_TICKED_COMMENT.format(user_login=pr_author)
            logger.info("Empty checklist: %s", pull_request["html_url"])

        if comment is not None:
            await utils.close_pr_or_issue(
                gh, comment=comment, pr_or_issue=pull_request, label=Label.INVALID
            )
            return None
        elif MAX_PR_PER_USER > 0:
            user_pr_numbers = await utils.get_user_open_pr_numbers(
                gh,
                repository=event.data["repository"]["full_name"],
                user_login=pr_author,
            )

            if len(user_pr_numbers) > MAX_PR_PER_USER:
                logger.info("Multiple open PRs: %s", pull_request["html_url"])
                # Convert list of numbers to: "#1, #2, #3"
                pr_number = "#{}".format(", #".join(map(str, user_pr_numbers)))
                await utils.close_pr_or_issue(
                    gh,
                    comment=MAX_PR_REACHED_COMMENT.format(
                        user_login=pr_author, pr_number=pr_number
                    ),
                    pr_or_issue=pull_request,
                )
                return None

    # We will check files only if the pull request is valid and thus, not closed.
    await check_pr_files(event, gh, *args, **kwargs)


@pull_request_router.register("pull_request", action="reopened")
@pull_request_router.register("pull_request", action="ready_for_review")
@pull_request_router.register("pull_request", action="synchronize")
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

    When a pull request is opened, this function will be triggered only if the
    pull request is considered valid. This function will also be triggered when a
    pull request is made ready for review, a new commit has been pushed to the
    pull request and when the pull request is reopened.
    """
    # When a bot pushes a commit to a pull request, don't perform any file checks.
    if (
        event.data["action"] == "synchronize"
        and event.data["sender"]["type"].lower() == "bot"
    ):
        return None

    pull_request = event.data["pull_request"]

    if pull_request["draft"]:
        return None

    ignore_modified: bool = kwargs.pop("ignore_modified", True)
    pr_files = await utils.get_pr_files(gh, pull_request=pull_request)
    parser = PythonParser(pr_files, pull_request)

    # No need to perform these checks every time a commit is pushed.
    if event.data["action"] != "synchronize":
        if pull_request["author_association"].lower() not in {"owner", "member"} and (
            invalid_files := parser.validate_extension()
        ):
            await utils.close_pr_or_issue(
                gh,
                comment=INVALID_EXTENSION_COMMENT.format(
                    user_login=pull_request["user"]["login"], files=invalid_files
                ),
                pr_or_issue=pull_request,
                label=Label.INVALID,
            )
            return None
        if label := parser.type_label():
            await utils.add_label_to_pr_or_issue(
                gh, label=label, pr_or_issue=pull_request
            )

    # Don't perform file checks if the pull request is made by a bot.
    if pull_request["user"]["type"].lower() == "bot":
        return None

    # Default behavior is to ignore modified files but that can be changed.
    # This will come only from the commands module through the command:
    # ``@algorithms-keeper review-all``
    for file in parser.files_to_check(ignore_modified):
        code = await utils.get_file_content(gh, file=file)
        parser.parse(file, code)

    if parser.labels_to_add:
        await utils.add_label_to_pr_or_issue(
            gh, label=parser.labels_to_add, pr_or_issue=pull_request
        )
    if parser.labels_to_remove:
        await utils.remove_label_from_pr_or_issue(
            gh, label=parser.labels_to_remove, pr_or_issue=pull_request
        )
    # We can only post the review comments on lines included in the pull request diff.
    # If the bot tries to post on lines not in the diff, GitHub will complain. So, we
    # will collect all the review content and post it as a single comment on the pull
    # request. This is triggered only by the ``@algorithms-keeper review-all`` command.
    if ignore_modified:
        if comments := parser.collect_comments():
            await utils.create_pr_review(
                gh, pull_request=pull_request, comments=comments
            )
    elif contents := parser.collect_review_contents():
        await utils.add_comment_to_pr_or_issue(
            gh,
            comment=PR_REVIEW_COMMENT.format(content="\n\n".join(contents)),
            pr_or_issue=pull_request,
        )


@pull_request_router.register("pull_request", action="ready_for_review")
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
    from algorithms_keeper.event.check_run import check_ci_status_and_label

    await check_ci_status_and_label(event, gh, *args, **kwargs)


@pull_request_router.register("pull_request_review", action="submitted")
async def update_pr_label_for_review(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Update the label for a pull request according to the review submitted. Reviews
    submitted by either the member or owner will count.

    - Ignore all the comments.
    - Add label when a maintainer request any changes.
    - Remove any awaiting labels, if present, when a maintainer approves.
    """
    pull_request = event.data["pull_request"]
    review = event.data["review"]
    review_state = review["state"]

    if review_state == "commented":
        return None

    if review["author_association"].lower() in {"member", "owner"}:
        if review_state == "changes_requested":
            await update_stage_label(
                gh, pull_request=pull_request, next_label=Label.CHANGE
            )
        elif review_state == "approved":
            await update_stage_label(gh, pull_request=pull_request)


@pull_request_router.register("pull_request", action="synchronize")
async def add_review_label_on_changes(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Add the `awaiting review` label once the author made the requested changes.

    NOTE: This will change the label on the first commit after a change has been
    requested, the author might not be ready by then.
    """
    pull_request = event.data["pull_request"]
    if pull_request["draft"]:
        return None
    await update_stage_label(gh, pull_request=pull_request, next_label=Label.REVIEW)


@pull_request_router.register("pull_request", action="closed")
async def remove_awaiting_labels(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Remove all awaiting labels.

    - When the pull request is merged.
    - If the pull request is invalid and got closed.
    """
    pull_request = event.data["pull_request"]
    if pull_request["merged"] or any(
        label["name"] == Label.INVALID for label in pull_request["labels"]
    ):
        await update_stage_label(gh, pull_request=pull_request)


@pull_request_router.register("pull_request", action="opened")
@pull_request_router.register("pull_request", action="reopened")
@pull_request_router.register("pull_request", action="synchronize")
async def check_merge_status(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Check the mergeability for the pull request.

    Add/remove the appropriate label to indicate the pull request contains merge
    conflicts.
    """
    pull_request = event.data["pull_request"]

    for retry_interval in range(MAX_RETRIES):
        mergeable: Optional[bool] = pull_request["mergeable"]
        if mergeable is None:
            # We will use the iter value we get as our sleep period between the polls.
            # In the webhook payload, the mergeable status will always be ``None``, so
            # in the first try the interval will be 0, thus requesting the pull request
            # without wasting any time and starting the background check on GitHub.
            # https://developer.github.com/v3/git/#checking-mergeability-of-pull-requests
            await asyncio.sleep(retry_interval)
            pull_request = await utils.update_pr(gh, pull_request=pull_request)
        else:
            current_labels: list[str] = [
                label["name"] for label in pull_request["labels"]
            ]
            if not mergeable:
                if Label.MERGE_CONFLICT not in current_labels:
                    await utils.add_label_to_pr_or_issue(
                        gh, label=Label.MERGE_CONFLICT, pr_or_issue=pull_request
                    )
            elif Label.MERGE_CONFLICT in current_labels:
                await utils.remove_label_from_pr_or_issue(
                    gh, label=Label.MERGE_CONFLICT, pr_or_issue=pull_request
                )
            break
