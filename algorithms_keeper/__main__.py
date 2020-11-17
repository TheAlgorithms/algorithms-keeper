import asyncio
import datetime
import os
from typing import Any

import aiohttp
import cachetools
import sentry_sdk
from aiohttp import web
from gidgethub import routing
from gidgethub.sansio import Event

from . import check_runs, installations, issues, pull_requests
from .api import GitHubAPI
from .log import CustomAccessLogger, logger

router = routing.Router(
    check_runs.router, installations.router, issues.router, pull_requests.router
)

cache = cachetools.LRUCache(maxsize=500)  # type: cachetools.LRUCache[Any, Any]

sentry_sdk.init(os.environ.get("SENTRY_DSN"))


async def main(request: web.Request) -> web.Response:
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        logger.info(
            "event=%(event)s delivery_id=%(delivery_id)s",
            {
                "event": f"{event.event}:{event.data['action']}",
                "delivery_id": event.delivery_id,
            },
        )
        async with aiohttp.ClientSession() as session:
            gh = GitHubAPI(
                event.data["installation"]["id"],
                session,
                "dhruvmanila/algorithms-keeper",
                cache=cache,
            )
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        try:
            logger.info(
                "ratelimit=%(ratelimit)s time_remaining=%(time_remaining)s",
                {
                    "ratelimit": f"{gh.rate_limit.remaining}/{gh.rate_limit.limit}",
                    "time_remaining": gh.rate_limit.reset_datetime
                    - datetime.datetime.now(datetime.timezone.utc),
                },
            )
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception as err:
        logger.exception(err)
        return web.Response(status=500, text=str(err))


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.router.add_post("/", main)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)  # type: ignore
    web.run_app(
        app,
        port=port,  # type: ignore
        access_log_class=CustomAccessLogger,
        access_log_format=CustomAccessLogger.LOG_FORMAT,
    )
