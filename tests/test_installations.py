import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import apps, sansio

from algorithms_keeper import installations
from algorithms_keeper.constants import GREETING_COMMENT

from .utils import MOCK_INSTALLATION_ID, MockGitHubAPI, mock_return

user = "test"
repository = "TheAlgorithms/Python"
number = 1

issue_url = f"/repos/{repository}/issues"
full_issue_url = f"https://api.github.com/repos/{repository}/issues/{number}"

GREETING_COMMENT = GREETING_COMMENT.format(login=user)


@pytest.fixture(scope="module", autouse=True)
def patch_module(monkeypatch=MonkeyPatch()):
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    yield monkeypatch
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_installation_created():
    data = {
        "action": "created",
        "installation": {"id": MOCK_INSTALLATION_ID},
        "repositories": [{"full_name": repository}],
        "sender": {"login": user},
    }
    event = sansio.Event(data, event="installation", delivery_id="1")
    post = {issue_url: {"url": full_issue_url}}
    patch = {full_issue_url: {"state": "closed"}}
    gh = MockGitHubAPI(post=post, patch=patch)
    await installations.router.dispatch(event, gh)
    assert issue_url in gh.post_url
    assert {
        "title": "Installation successful!",
        "body": GREETING_COMMENT,
    } in gh.post_data
    assert full_issue_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data


@pytest.mark.asyncio
async def test_installation_repositories_added():
    data = {
        "action": "added",
        "installation": {"id": MOCK_INSTALLATION_ID},
        "repositories_added": [{"full_name": repository}],
        "sender": {"login": user},
    }
    event = sansio.Event(data, event="installation_repositories", delivery_id="1")
    post = {issue_url: {"url": full_issue_url}}
    patch = {full_issue_url: {"state": "closed"}}
    gh = MockGitHubAPI(post=post, patch=patch)
    await installations.router.dispatch(event, gh)
    assert issue_url in gh.post_url
    assert {
        "title": "Installation successful!",
        "body": GREETING_COMMENT,
    } in gh.post_data
    assert full_issue_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
