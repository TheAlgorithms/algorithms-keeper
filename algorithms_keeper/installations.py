from typing import Any

from gidgethub import routing
from gidgethub.sansio import Event

from .api import GitHubAPI
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
    try:
        repositories = event.data["repositories"]
    except KeyError:
        repositories = event.data["repositories_added"]

    for repository in repositories:
        response = await gh.post(
            f"/repos/{repository['full_name']}/issues",
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
