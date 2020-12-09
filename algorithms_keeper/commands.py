"""Bot commands module

``@algorithms-keeper review`` to trigger the checks for pull request files.
"""
import re
from typing import Any

from gidgethub import routing
from gidgethub.sansio import Event

from algorithms_keeper import utils
from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.log import logger
from algorithms_keeper.pull_requests import check_pr_files

router = routing.Router()

COMMAND_RE = re.compile(r"@algorithms[\-_]keeper\s+([a-z]+)", re.IGNORECASE)


@router.register("issue_comment", action="created")
async def review(event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any) -> None:
    """Review command to trigger the checks for pull request files."""
    comment = event.data["comment"]

    if comment["author_association"].lower() not in {"member", "owner"}:
        return None

    if match := COMMAND_RE.search(comment["body"]):
        command = match.group(1).lower()
        logger.info(
            "match=%(match)s command=%(command)s %(url)s",
            {"match": match.string, "command": command, "url": comment["html_url"]},
        )
        if command == "review":
            await utils.add_reaction(gh, reaction="+1", comment=comment)
            event.data["pull_request"] = await utils.get_pr_for_issue(
                gh, issue=event.data["issue"]
            )
            await check_pr_files(event, gh, *args, **kwargs)
