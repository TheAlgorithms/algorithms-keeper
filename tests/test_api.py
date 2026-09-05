import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from gidgethub import apps, sansio

from algorithms_keeper.api import GitHubAPI, token_cache

from .utils import number, token


async def mock_return(*args: Any, **kwargs: Any) -> Dict[str, str]:
    return {"token": token}


@pytest_asyncio.fixture
async def github_api() -> AsyncGenerator[GitHubAPI, None]:
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(number, session, "algorithms-keeper")
        yield gh
    assert session.closed is True


@pytest.mark.asyncio()
async def test_initialization() -> None:
    async with aiohttp.ClientSession() as session:
        github_api = GitHubAPI(number, session, "algorithms-keeper")
    # First layer is initialized
    assert github_api._installation_id == number
    # Second layer is initialized
    assert github_api._session == session
    # Abstract layer is initialized
    assert github_api.requester == "algorithms-keeper"


@pytest.mark.asyncio()
async def test_access_token(
    github_api: GitHubAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    monkeypatch.setenv("GITHUB_APP_ID", "")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "")
    token_cache.clear()  # Make sure the token_cache is cleared
    access_token = await github_api.access_token
    assert access_token == token
    # This is to make sure it actually returns the cached token
    monkeypatch.delattr(apps, "get_installation_access_token")
    cached_token = await github_api.access_token
    assert cached_token == token


@pytest.mark.asyncio()
async def test_request_with_local_server(
    github_api: GitHubAPI, aiohttp_server: Callable[..., Awaitable[TestServer]]
) -> None:
    # Exercise the session fixture and server fixture on the test's running loop.
    async def handler(request: web.Request) -> web.Response:
        assert request.headers["X-Test"] == "loop-lifecycle"
        assert await request.read() == b"request body"
        return web.Response(body=b"response body", headers={"X-Test": "response"})

    app = web.Application()
    app.router.add_post("/", handler)
    server = await aiohttp_server(app)
    status, headers, body = await github_api._request(
        "POST", str(server.make_url("/")), {"X-Test": "loop-lifecycle"}, b"request body"
    )
    assert status == 200
    assert headers["X-Test"] == "response"
    assert body == b"response body"


@pytest.mark.asyncio()
async def test_headers_and_log(github_api: GitHubAPI) -> None:
    request_headers = sansio.create_headers("algorithms-keeper")
    resp = await github_api._request(
        "GET", "https://api.github.com/rate_limit", request_headers
    )
    data, rate_limit, _ = sansio.decipher_response(*resp)
    assert "rate" in data


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "request_args, response_args, expected_level",
    [
        (
            ("DELETE", "/repos/org/repo/issues/1/labels/tests%20are%20failing"),
            (404, b'{"message": "Label does not exist"}'),
            logging.INFO,
        ),
        (
            ("DELETE", "/repos/org/repo/issues/1/labels/tests%20are%20failing"),
            (404, b'{"message": "Not Found"}'),
            logging.ERROR,
        ),
        (
            ("DELETE", "/repos/org/repo/issues/1/labels/tests%20are%20failing"),
            (403, b'{"message": "Label does not exist"}'),
            logging.ERROR,
        ),
        (
            ("POST", "/repos/org/repo/issues/1/labels/tests%20are%20failing"),
            (404, b'{"message": "Label does not exist"}'),
            logging.ERROR,
        ),
        (
            ("DELETE", "/repos/org/repo/labels/tests%20are%20failing"),
            (404, b'{"message": "Label does not exist"}'),
            logging.ERROR,
        ),
        (
            ("DELETE", "/repos/org/repo/issues/1/labels/tests%20are%20failing"),
            (404, b"not json"),
            logging.ERROR,
        ),
        (
            ("DELETE", "/repos/org/repo/issues/1/labels/tests%20are%20failing"),
            (404, b"[]"),
            logging.ERROR,
        ),
    ],
)
async def test_label_removal_logging(
    request_args: tuple[str, str],
    response_args: tuple[int, bytes],
    expected_level: int,
    github_api: GitHubAPI,
    aiohttp_server: Callable[..., Awaitable[TestServer]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    response_status, response_body = response_args

    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=response_status, body=response_body)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    server = await aiohttp_server(app)
    method, path = request_args
    with caplog.at_level(logging.INFO, logger="algorithms_keeper"):
        status, _, body = await github_api._request(
            method, str(server.make_url(path)), {}
        )

    assert status == response_status
    assert body == response_body
    records = [
        record for record in caplog.records if record.name == "algorithms_keeper"
    ]
    assert len(records) == 1
    assert records[0].levelno == expected_level
