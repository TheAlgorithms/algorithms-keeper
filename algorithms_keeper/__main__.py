import asyncio
import datetime
import os
from typing import Any

import sentry_sdk
from aiohttp import ClientSession
from aiohttp.web import Application, Request, Response, run_app
from cachetools import LRUCache
from gidgethub import routing
from gidgethub.sansio import Event
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from algorithms_keeper import check_runs, installations, issues, pull_requests
from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.log import CustomAccessLogger, logger

router = routing.Router(
    check_runs.router, installations.router, issues.router, pull_requests.router
)

cache: LRUCache[Any, Any] = LRUCache(maxsize=500)

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[AioHttpIntegration(transaction_style="method_and_path_pattern")],
)


async def main(request: Request) -> Response:
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return Response(status=200)
        logger.info(
            "event=%(event)s delivery_id=%(delivery_id)s",
            {
                "event": f"{event.event}:{event.data['action']}",
                "delivery_id": event.delivery_id,
            },
        )
        async with ClientSession() as session:
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
        return Response(status=200)
    except Exception as err:
        logger.exception(err)
        return Response(status=500, text=str(err))


if __name__ == "__main__":  # pragma: no cover
    app = Application()
    app.router.add_post("/", main)
    run_app(
        app,
        access_log_class=CustomAccessLogger,
        access_log_format=CustomAccessLogger.LOG_FORMAT,
    )
