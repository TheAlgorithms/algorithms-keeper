import aiohttp
import pytest
from gidgethub import apps, sansio

from algorithms_keeper import api

from .utils import mock_return, number, token


@pytest.fixture
async def github_api():
    try:
        async with aiohttp.ClientSession() as session:
            gh = api.GitHubAPI(number, session, "algorithms-keeper")
            yield gh
    finally:
        assert session.closed is True


@pytest.mark.asyncio
async def test_initialization():
    async with aiohttp.ClientSession() as session:
        github_api = api.GitHubAPI(number, session, "algorithms-keeper")
    # First layer is initialized
    assert github_api._installation_id == number
    # Second layer is initialized
    assert github_api._session == session
    # Abstract layer is initialized
    assert github_api.requester == "algorithms-keeper"
    # Response headers should not be set yet.
    assert github_api.headers is None


@pytest.mark.asyncio
async def test_read_only_property(github_api):
    with pytest.raises(AttributeError):
        github_api.headers = "something"
    with pytest.raises(AttributeError):
        github_api.access_token = "shhhhh"


@pytest.mark.asyncio
async def test_access_token(github_api, monkeypatch):
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    monkeypatch.setenv("GITHUB_APP_ID", "")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "")
    api.token_cache.clear()  # Make sure the token_cache is cleared
    access_token = await github_api.access_token
    assert access_token == token
    # This is to make sure it actually returns the cached token
    monkeypatch.delattr(apps, "get_installation_access_token")
    cached_token = await github_api.access_token
    assert cached_token == token
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_headers_and_log(github_api):
    assert github_api.headers is None
    request_headers = sansio.create_headers("algorithms-keeper")
    resp = await github_api._request(
        "GET", "https://api.github.com/rate_limit", request_headers
    )
    data, rate_limit, _ = sansio.decipher_response(*resp)
    assert "rate" in data
    assert github_api.headers is not None
