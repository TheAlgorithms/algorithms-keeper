import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping

from aiohttp import ClientSession, web
from cachetools import LRUCache
from gidgethub.sansio import Event
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.event import main_router

# TODO(dhruvmanila): Remove this block when it's the default.
# https://github.com/Instagram/LibCST/issues/285#issuecomment-1011427731
if sys.version_info >= (3, 10):
    os.environ["LIBCST_PARSER_TYPE"] = "native"

cache: MutableMapping[Any, Any] = LRUCache(maxsize=500)

sentry_init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[AioHttpIntegration(transaction_style="method_and_path_pattern")],
)

logging.basicConfig(
    format="[%(levelname)s] %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO"),
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__package__)

routes = web.RouteTableDef()

STATIC_DIR = Path(__file__).parent / "static"


@routes.get("/")
async def index(_: web.Request) -> web.Response:
    commit = os.getenv("RENDER_GIT_COMMIT", "???")
    content = (
        STATIC_DIR.joinpath("index.html")
        .read_text()
        .replace("{{ commit }}", commit)
        .replace("{{ short_commit }}", commit[:7])
    )
    return web.Response(body=content, content_type="text/html")


@routes.get("/favicon.ico")
async def favicon(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR.joinpath("favicon.ico"))


@routes.get("/health")
async def health(_: web.Request) -> web.Response:
    return web.Response(status=200, text="OK")


@routes.post("/")
async def main(request: web.Request) -> web.Response:
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            logger.debug("Received ping event")
            return web.Response(status=200, text="pong")
        event_info = f"{event.event}:{event.data['action']}"
        logger.info("event=%s delivery_id=%s", event_info, event.delivery_id)
        async with ClientSession() as session:
            gh = GitHubAPI(
                installation_id=event.data["installation"]["id"],
                session=session,
                requester="TheAlgorithms/algorithms-keeper",
                cache=cache,
            )
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            if logger.isEnabledFor(logging.DEBUG):
                callbacks = [func.__name__ for func in main_router.fetch(event)]
                logger.debug("event=%s callbacks=%s", event_info, callbacks)
            await main_router.dispatch(event, gh)
        if gh.rate_limit is not None:  # pragma: no cover
            logger.info(
                "ratelimit=%s, time_remaining=%s",
                f"{gh.rate_limit.remaining}/{gh.rate_limit.limit}",
                gh.rate_limit.reset_datetime - datetime.now(timezone.utc),
            )
        return web.Response(status=200)
    except Exception as err:
        logger.exception(err)
        return web.Response(status=500, text=str(err))


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.add_routes(routes)
    # Heroku dynamically assigns the app a port, so we can't set the port to a fixed
    # number. Heroku adds the port to the env, so we need to pull it from there.
    web.run_app(app, port=int(os.environ.get("PORT", 5000)))
