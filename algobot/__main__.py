import asyncio
import os
import sys
import traceback

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

cache = cachetools.LRUCache(maxsize=500)

# Create a route table
# Use the decorator .get, .post, ... to add all the routes to the table
routes = web.RouteTableDef()


@routes.get("/", name="home")
async def handle_get(request):
    return web.Response(text="Hello world")


@routes.post("/webhook")
async def webhook(request):
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "demo", cache=cache)

            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        try:
            print("GH requests remaining:", gh.rate_limit.remaining)
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


@router.register("installation", action="created")
@router.register("installation_repositories", action="added")
async def repo_installation_added(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, *args, **kwargs
):
    """Give the repository a heads up that the app has been installed.

    :param event: Representation of GitHub's webhook event, access it with event.data
    :param gh: :class:`gidget.aiohttp.GitHubAPI`, gidgethub GitHub API object
    """
    installation_id = event.data["installation"]["id"]
    installation_access_token = await apps.get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=os.environ.get("GITHUB_APP_ID"),
        private_key=os.environ.get("GITHUB_PRIVATE_KEY"),
    )
    sender_name = event.data["sender"]["login"]
    try:
        repositories = event.data["repositores"]
    except KeyError:
        repositories = event.data["repositories_added"]

    for repository in repositories:
        url = f"/repos/{repository['full_name']}/issues"
        response = await gh.post(
            url,
            data={
                "title": "Installation successful!",
                "body": f"This is the Algorithms bot at your service! Thank you for installing me @{sender_name}",
            },
            oauth_token=installation_access_token["token"],
        )
        issue_url = response["url"]
        await gh.patch(
            issue_url,
            data={"state": "closed"},
            oauth_token=installation_access_token["token"],
        )


if __name__ == "__main__":  # pragma: no cover
    # Create an web Application instance
    app = web.Application()
    # Add the route table to our app
    app.router.add_routes(routes)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    web.run_app(app, port=port)
