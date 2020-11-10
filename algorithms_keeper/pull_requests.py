import re
from pathlib import PurePath
from typing import Any

from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing, sansio

from . import utils
from .comments import (
    CHECKBOX_NOT_TICKED_COMMENT,
    EMPTY_BODY_COMMENT,
    MAX_PR_REACHED_COMMENT,
    NO_EXTENSION_COMMENT,
    PR_REPORT_COMMENT,
)
from .logging import logger
from .parser import PullRequestFilesParser

MAX_PR_PER_USER = 1

router = routing.Router()


@router.register("pull_request", action="opened")
@router.register("pull_request", action="ready_for_review")
async def close_invalid_or_additional_pr(
    event: sansio.Event,
    gh: gh_aiohttp.GitHubAPI,
    *args: Any,
    **kwargs: Any,
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

    # Ignore draft pull requests
    if pull_request["draft"]:
        print(f"[SKIPPED] Draft pull request: {pull_request['html_url']}")
        return None

    author_association = pull_request["author_association"].lower()
    if author_association in {"owner", "member"}:
        logger.info(
            "Author association %r: %s", author_association, pull_request["html_url"]
        )
        return None

    pr_body = pull_request["body"]
    pr_author = pull_request["user"]["login"]
    comment = None

    if not pr_body:
        comment = EMPTY_BODY_COMMENT.format(user_login=pr_author)
        logger.info("Empty PR body: %s", pull_request["html_url"])
    elif not re.search(r"\[x]", pr_body):
        comment = CHECKBOX_NOT_TICKED_COMMENT.format(user_login=pr_author)
        logger.info("Empty checklist: %s", pull_request["html_url"])

    if comment:
        await utils.close_pr_or_issue(
            gh,
            installation_id,
            comment=comment,
            pr_or_issue=pull_request,
            label="invalid",
        )
    elif MAX_PR_PER_USER > 0:
        user_pr_numbers = await utils.get_total_open_prs(
            gh,
            installation_id,
            repository=event.data["repository"]["full_name"],
            user_login=pr_author,
            count=False,
        )

        if len(user_pr_numbers) > MAX_PR_PER_USER:
            logger.info("Multiple open PRs: %s", pull_request["html_url"])
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


@router.register("pull_request", action="opened")
@router.register("pull_request", action="ready_for_review")
@router.register("pull_request", action="synchronize")
async def check_pr_files(
    event: sansio.Event,
    gh: gh_aiohttp.GitHubAPI,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Check all the pull request files for extension, type hints, tests and
    class, function and parameter names.

    This function will accomplish the following tasks:
    - Check for file extension and close the pull request if a file do not contain any
      extension. Ignores all non-python files and any file in `.github` directory.
    - Check for type hints, tests and descriptive names in the submitted files and
      label it appropriately. Sends the report if there are any errors only when the
      pull request is opened.

    This function will also be triggered when new commits are pushed to the opened pull
    request.
    """
    installation_id = event.data["installation"]["id"]
    pull_request = event.data["pull_request"]

    # Ignore draft pull requests
    if pull_request["draft"]:
        # This message is already being logged by the above function
        if event.data["action"] == "synchronize":
            print(f"[SKIPPED] Draft pull request: {pull_request['html_url']}")
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
        filepath = PurePath(file["filename"])
        if not filepath.suffix and ".github" not in filepath.parts:
            logger.info(
                "No extension file %r: %s", file["filename"], pull_request["html_url"]
            )
            await utils.close_pr_or_issue(
                gh,
                installation_id,
                comment=NO_EXTENSION_COMMENT.format(user_login=pr_author),
                pr_or_issue=pull_request,
                label="invalid",
            )
            return None
        elif filepath.suffix != ".py" or filepath.name.startswith("__"):
            continue
        # If there is a test file then we do not want to check for `doctest`.
        # NOTE: This should come after the check for `.py` files.
        elif filepath.name.startswith("test_") or filepath.name.endswith("_test.py"):
            parser.skip_doctest = True
        files_to_check.append(file)

    for file in files_to_check:
        code = await utils.get_file_content(gh, installation_id, file=file)
        parser.parse_code(file["filename"], code)

    labels_to_add, labels_to_remove = parser.labels_to_add_and_remove(pr_labels)

    if labels_to_add:
        await utils.add_label_to_pr_or_issue(
            gh, installation_id, label=labels_to_add, pr_or_issue=pull_request
        )

    if labels_to_remove:
        await utils.remove_label_from_pr_or_issue(
            gh, installation_id, label=labels_to_remove, pr_or_issue=pull_request
        )

    # Comment the report data only when the pull request is opened or made
    # 'ready_for_review' after being in draft mode and if there are any errors
    if event.data["action"] in {"opened", "ready_for_review"}:
        report_content = parser.create_report_content()
        if report_content:
            logger.info(
                "Missing requirements in parsed files %s: %s",
                [file["filename"] for file in files_to_check],
                pull_request["html_url"],
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
    event: sansio.Event,
    gh: gh_aiohttp.GitHubAPI,
    *args: Any,
    **kwargs: Any,
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
