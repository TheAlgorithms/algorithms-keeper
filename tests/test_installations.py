import pytest
from gidgethub import sansio

from algorithms_keeper import installations
from algorithms_keeper.constants import GREETING_COMMENT

from .utils import MockGitHubAPI, issue_path, issue_url, number, repository, user

GREETING_COMMENT = GREETING_COMMENT.format(login=user)


@pytest.mark.asyncio
async def test_installation_created():
    data = {
        "action": "created",
        "installation": {"id": number},
        "repositories": [{"full_name": repository}],
        "sender": {"login": user},
    }
    event = sansio.Event(data, event="installation", delivery_id="1")
    post = {issue_path: {"url": issue_url}}
    patch = {issue_url: None}
    gh = MockGitHubAPI(post=post, patch=patch)
    await installations.router.dispatch(event, gh)
    assert issue_path in gh.post_url
    assert {
        "title": "Installation successful!",
        "body": GREETING_COMMENT,
    } in gh.post_data
    assert issue_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data


@pytest.mark.asyncio
async def test_installation_repositories_added():
    data = {
        "action": "added",
        "installation": {"id": number},
        "repositories_added": [{"full_name": repository}],
        "sender": {"login": user},
    }
    event = sansio.Event(data, event="installation_repositories", delivery_id="1")
    post = {issue_path: {"url": issue_url}}
    patch = {issue_url: None}
    gh = MockGitHubAPI(post=post, patch=patch)
    await installations.router.dispatch(event, gh)
    assert issue_path in gh.post_url
    assert {
        "title": "Installation successful!",
        "body": GREETING_COMMENT,
    } in gh.post_data
    assert issue_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
