from typing import Any, AsyncGenerator, Dict

import aiohttp
import pytest
import pytest_asyncio
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
async def test_headers_and_log(github_api: GitHubAPI) -> None:
    request_headers = sansio.create_headers("algorithms-keeper")
    resp = await github_api._request(
        "GET", "https://api.github.com/rate_limit", request_headers
    )
    data, rate_limit, _ = sansio.decipher_response(*resp)
    assert "rate" in data
