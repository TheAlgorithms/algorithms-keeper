from typing import Any

from gidgethub import routing
from gidgethub.aiohttp import GitHubAPI
from gidgethub.sansio import Event

from . import utils
from .constants import GREETING_COMMENT

router = routing.Router()


@router.register("installation", action="created")
@router.register("installation_repositories", action="added")
async def repo_installation_added(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Give the repository a heads up that the app has been installed.

    This callback will be triggered by two events:
    1. When a new installation for this app is added
    2. When a new repository is added in an existing installation
    """
    installation_id = event.data["installation"]["id"]
    installation_access_token = await utils.get_access_token(gh, installation_id)
    sender_name = event.data["sender"]["login"]
    try:
        repositories = event.data["repositories"]
    except KeyError:
        repositories = event.data["repositories_added"]

    for repository in repositories:
        response = await gh.post(
            f"/repos/{repository['full_name']}/issues",
            data={
                "title": "Installation successful!",
                "body": GREETING_COMMENT.format(login=sender_name),
            },
            oauth_token=installation_access_token,
        )
        issue_url = response["url"]
        await gh.patch(
            issue_url,
            data={"state": "closed"},
            oauth_token=installation_access_token,
        )
