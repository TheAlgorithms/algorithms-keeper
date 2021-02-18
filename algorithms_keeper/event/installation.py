import logging
from typing import Any

from gidgethub import routing
from gidgethub.sansio import Event

from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.constants import GREETING_COMMENT

installation_router = routing.Router()

logger = logging.getLogger(__package__)


@installation_router.register("installation", action="created")
@installation_router.register("installation_repositories", action="added")
async def repo_installation_added(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Give the repository a heads up that the app has been installed.

    This callback will be triggered by two events:
    1. When a new installation for this app is added
    2. When a new repository is added in an existing installation
    """
    try:
        repositories = event.data["repositories"]
    except KeyError:
        repositories = event.data["repositories_added"]

    for repository in repositories:
        repo_name = repository["full_name"]
        logger.info("New repository added: %s", repo_name)
        response = await gh.post(
            f"/repos/{repo_name}/issues",
            data={
                "title": "Installation successful!",
                "body": GREETING_COMMENT.format(login=event.data["sender"]["login"]),
            },
            oauth_token=await gh.access_token,
        )
        issue_url = response["url"]
        await gh.patch(
            issue_url, data={"state": "closed"}, oauth_token=await gh.access_token
        )
