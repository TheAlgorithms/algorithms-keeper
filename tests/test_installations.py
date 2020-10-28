import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import apps, sansio

from algobot import installations

from .utils import MOCK_INSTALLATION_ID, MockGitHubAPI, mock_return


def setup_module(module, monkeypatch=MonkeyPatch()):
    """Monkeypatch for this module to store the MOCK_TOKEN in cache.

    We cannot use `pytest.fixture(scope="module")` as `monkeypatch` fixture
    only works at function level (this is a module level setup function),
    so we will directly use the MonkeyPatch class where the fixture is
    generated from and pass it as the default argument to this function.

    This will only be executed once in this module, storing the token in the
    cache for later use.
    """
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)


@pytest.mark.asyncio
async def test_installation_created():
    repository = "dhruvmanila/testing"
    data = {
        "action": "created",
        "installation": {"id": MOCK_INSTALLATION_ID},
        "repositories": [{"full_name": repository}],
        "sender": {"login": "dhruvmanila"},
    }
    event = sansio.Event(data, event="installation", delivery_id="1")

    post = {
        "url": "https://api.github.com/repos/dhruvmanila/testing/issues/8",
        "number": 8,
        "title": "Installation successful!",
        "user": {"login": "algorithms-bot[bot]", "type": "Bot"},
        "state": "open",
        "body": (
            "This is the Algorithms bot at your service! "
            "Thank you for installing me @dhruvmanila"
        ),
    }
    patch = {
        "url": "https://api.github.com/repos/dhruvmanila/testing/issues/8",
        "number": 8,
        "title": "Installation successful!",
        "user": {"login": "algorithms-bot[bot]", "type": "Bot"},
        "state": "closed",
        "body": (
            "This is the Algorithms bot at your service! "
            "Thank you for installing me @dhruvmanila"
        ),
    }

    gh = MockGitHubAPI(post=post, patch=patch)
    await installations.router.dispatch(event, gh)
    assert gh.post_url == f"/repos/{repository}/issues"
    assert gh.post_data["title"] == "Installation successful!"
    assert gh.post_data["body"] == (
        "This is the Algorithms bot at your service! "
        "Thank you for installing me @dhruvmanila"
    )
    assert gh.patch_url == "https://api.github.com/repos/dhruvmanila/testing/issues/8"
    assert gh.patch_data["state"] == "closed"


@pytest.mark.asyncio
async def test_installation_repositories_added():
    repository = "dhruvmanila/testing"
    data = {
        "action": "added",
        "installation": {"id": MOCK_INSTALLATION_ID},
        "repositories_added": [{"full_name": repository}],
        "sender": {"login": "dhruvmanila"},
    }
    event = sansio.Event(data, event="installation_repositories", delivery_id="2")

    post = {
        "url": "https://api.github.com/repos/dhruvmanila/testing/issues/8",
        "number": 8,
        "title": "Installation successful!",
        "user": {"login": "algorithms-bot[bot]", "type": "Bot"},
        "state": "open",
        "body": (
            "This is the Algorithms bot at your service! "
            "Thank you for installing me @dhruvmanila"
        ),
    }
    patch = {
        "url": "https://api.github.com/repos/dhruvmanila/testing/issues/8",
        "number": 8,
        "title": "Installation successful!",
        "user": {"login": "algorithms-bot[bot]", "type": "Bot"},
        "state": "closed",
        "body": (
            "This is the Algorithms bot at your service! "
            "Thank you for installing me @dhruvmanila"
        ),
    }

    gh = MockGitHubAPI(post=post, patch=patch)
    await installations.router.dispatch(event, gh)
    assert gh.post_url == f"/repos/{repository}/issues"
    assert gh.post_data["title"] == "Installation successful!"
    assert gh.post_data["body"] == (
        "This is the Algorithms bot at your service! "
        "Thank you for installing me @dhruvmanila"
    )
    assert gh.patch_url == "https://api.github.com/repos/dhruvmanila/testing/issues/8"
    assert gh.patch_data["state"] == "closed"
