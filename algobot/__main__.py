import asyncio
import datetime
import os
import sys
import traceback

import aiohttp
import cachetools
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing, sansio

from . import check_runs, installations, pull_requests

router = routing.Router(installations.router, check_runs.router, pull_requests.router)

cache = cachetools.LRUCache(maxsize=500)  # type: cachetools.LRUCache


async def main(request: web.Request) -> web.Response:
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        print(
            f"Received {event.event + ':' + event.data['action']!r} event "
            f"with delivery ID: {event.delivery_id}"
        )
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "algorithms-bot", cache=cache)
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        try:
            time_remaining = gh.rate_limit.reset_datetime - datetime.datetime.now(
                datetime.timezone.utc
            )
            print(f"GH Ratelimit: {gh.rate_limit} (UTC) which is in {time_remaining}")
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.router.add_post("/webhook", main)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)  # type: ignore
    web.run_app(app, port=port)
