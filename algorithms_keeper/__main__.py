import os
from asyncio import sleep as async_sleep
from datetime import datetime, timezone
from typing import Any, MutableMapping

from aiohttp import ClientSession
from aiohttp.web import Application, Request, Response, run_app
from cachetools import LRUCache
from gidgethub import routing
from gidgethub.sansio import Event
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from algorithms_keeper import check_runs, installations, issues, pull_requests
from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.log import CustomAccessLogger, logger

router = routing.Router(
    check_runs.router, installations.router, issues.router, pull_requests.router
)

cache: MutableMapping[Any, Any] = LRUCache(maxsize=500)

sentry_init(
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
            await async_sleep(1)
            await router.dispatch(event, gh)
        if gh.rate_limit is not None:  # pragma: no cover
            logger.info(
                "ratelimit=%(ratelimit)s time_remaining=%(time_remaining)s",
                {
                    "ratelimit": f"{gh.rate_limit.remaining}/{gh.rate_limit.limit}",
                    "time_remaining": gh.rate_limit.reset_datetime
                    - datetime.now(timezone.utc),
                },
            )
        return Response(status=200)
    except Exception as err:
        logger.exception(err)
        return Response(status=500, text=str(err))


if __name__ == "__main__":  # pragma: no cover
    app = Application()
    app.router.add_post("/", main)
    # Heroku dynamically assigns the app a port, so we can't set the port to a fixed
    # number. Heroku adds the port to the env, so we need to pull it from there.
    run_app(
        app,
        port=int(os.environ.get("PORT", 5000)),
        access_log_class=CustomAccessLogger,
        access_log_format=CustomAccessLogger.LOG_FORMAT,
    )
