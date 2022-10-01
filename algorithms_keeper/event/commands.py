"""algorithms-keeper commands module

``@algorithms-keeper review`` to trigger the checks for only added pull request files.
``@algorithms-keeper review-all`` to trigger the checks for all the pull request files,
including the modified files. As we cannot post review comments on lines not part of
the diff, this command only modify the labels accordingly.
"""
import logging
import re
from typing import Any, Pattern

from gidgethub import routing
from gidgethub.sansio import Event

from algorithms_keeper import utils
from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.event.pull_request import check_pr_files

commands_router = routing.Router()

COMMAND_RE: Pattern[str] = re.compile(r"@algorithms-keeper\s+([a-z\-]+)", re.IGNORECASE)

logger = logging.getLogger(__package__)


@commands_router.register("issue_comment", action="created")
async def check_comment_for_command(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Main function to parse the comment body and call the respective command
    function if it matches.

    Only the comments made by either the member or the owner of the organization will
    be considered.
    """
    comment = event.data["comment"]

    if comment["author_association"].lower() not in {"member", "owner"}:
        return None

    if match := COMMAND_RE.search(comment["body"]):
        command = match.group(1).lower()
        logger.info("match=%s command=%s", match.string, command)
        if command == "review":
            await review(event, gh, *args, **kwargs)
        elif command == "review-all":
            await review(event, gh, *args, ignore_modified=False, **kwargs)


async def review(event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any) -> None:
    """Review command to trigger the checks for all the pull request files."""
    issue = event.data["issue"]
    comment = event.data["comment"]
    if "pull_request" in issue:
        # Give a heads up that the command has been received.
        await utils.add_reaction(gh, reaction="+1", comment=comment)
        event.data["pull_request"] = await utils.get_pr_for_issue(gh, issue=issue)
        await check_pr_files(event, gh, *args, **kwargs)
    else:
        # The command cannot be run on an issue.
        await utils.add_reaction(gh, reaction="-1", comment=comment)
