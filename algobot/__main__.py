import asyncio
import os
import sys
import traceback
from typing import Any

import aiohttp
from aiohttp import web
import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio
from gidgethub import apps

# Create a Router instance
# This allows for individual async functions to be written per event type
# to help keep logic separated and focused instead of having to differentiate
# between different events manually in user code.
router = routing.Router()

cache = cachetools.LRUCache(maxsize=500)  # type: cachetools.LRUCache


async def main(request: web.Request) -> web.Response:
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        print("GH delivery ID:", event.delivery_id, file=sys.stderr)
        if event.event == "ping":
            return web.Response(status=200)
        oauth_token = os.environ.get("GITHUB_OAUTH_TOKEN")
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(
                session, "TheAlgorithms/Python", oauth_token=oauth_token, cache=cache
            )
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        try:
            print(
                f"GH requests remaining: {gh.rate_limit.remaining}\n"
                f"Reset time: {gh.rate_limit.reset_datetime:%b-%d-%Y %H:%M:%S %Z}\n"
                f"oauth token length: {len(oauth_token)}\n"
                f"Last 4 digits: {oauth_token[-4:]}\n"
                f"GH delivery ID: {event.delivery_id}\n"
            )
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


@router.register("installation", action="created")
@router.register("installation_repositories", action="added")
async def repo_installation_added(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, *args: Any, **kwargs: Any
):
    """Give the repository a heads up that the app has been installed.

    :param event: :class:`gidgethub.sansio.Event`,
                Representation of GitHub's webhook event, access it with event.data
    :param gh: :class:`gidget.aiohttp.GitHubAPI`, gidgethub GitHub API object
    """
    # installation_id = event.data["installation"]["id"]
    # installation_access_token = await apps.get_installation_access_token(
    #     gh,
    #     installation_id=installation_id,
    #     app_id=os.environ.get("GITHUB_APP_ID"),
    #     private_key=os.environ.get("GITHUB_PRIVATE_KEY"),
    # )
    sender_name = event.data["sender"]["login"]
    try:
        repositories = event.data["repositories"]
    except KeyError:
        repositories = event.data["repositories_added"]

    for repository in repositories:
        url = f"/repos/{repository['full_name']}/issues"
        response = await gh.post(
            url,
            data={
                "title": "Installation successful!",
                "body": (
                    f"This is the Algorithms bot at your service! "
                    f"Thank you for installing me @{sender_name}"
                ),
            },
            # oauth_token=installation_access_token["token"],
        )
        issue_url = response["url"]
        await gh.patch(
            issue_url,
            data={"state": "closed"},
            # oauth_token=installation_access_token["token"],
        )


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.router.add_post("/", main)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)  # type: ignore
    web.run_app(app, port=port)
