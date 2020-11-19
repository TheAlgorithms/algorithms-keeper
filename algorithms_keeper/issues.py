from typing import Any

from gidgethub import routing
from gidgethub.aiohttp import GitHubAPI
from gidgethub.sansio import Event

from . import utils
from .comments import EMPTY_ISSUE_BODY_COMMENT
from .constants import Label
from .log import logger

router = routing.Router()


@router.register("issues", action="opened")
async def close_invalid_issue(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Close an invalid issue.

    An issue is considered invalid if:
    - It doesn't contain any description.
    """
    installation_id = event.data["installation"]["id"]
    issue = event.data["issue"]

    if not issue["body"]:
        logger.info("Empty issue body: %(url)s", {"url": issue["html_url"]})
        await utils.close_pr_or_issue(
            gh,
            installation_id,
            comment=EMPTY_ISSUE_BODY_COMMENT.format(user_login=issue["user"]["login"]),
            pr_or_issue=issue,
            label=Label.INVALID,
        )
