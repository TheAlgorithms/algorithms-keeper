import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import apps, sansio

from algorithms_keeper import issues
from algorithms_keeper.comments import EMPTY_ISSUE_BODY_COMMENT
from algorithms_keeper.constants import Label

from .utils import MOCK_INSTALLATION_ID, MockGitHubAPI, mock_return

# Common constants
number = 1
user = "test"
repository = "TheAlgorithms/Python"

# Complete urls
issue_url = f"https://api.github.com/repos/{repository}/issues/{number}"
html_issue_url = f"https://github.com/{repository}/issues/{number}"
labels_url = issue_url + "/labels"
comments_url = issue_url + "/comments"

# Comments constant
EMPTY_ISSUE_BODY_COMMENT = EMPTY_ISSUE_BODY_COMMENT.format(user_login=user)


@pytest.fixture(scope="module", autouse=True)
def patch_module(monkeypatch=MonkeyPatch()):
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    yield monkeypatch
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_empty_issue_body():
    data = {
        "action": "opened",
        "issue": {
            "url": issue_url,
            "number": number,
            "comments_url": comments_url,
            "labels_url": labels_url,
            "user": {"login": user},
            "body": "",
            "html_url": html_issue_url,
        },
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="issues", delivery_id="1")
    post = {comments_url: {}, labels_url: {}}
    patch = {issue_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    await issues.router.dispatch(event, gh)
    assert gh.getitem_url == []
    assert gh.getiter_url == []
    assert len(gh.post_url) == 2
    assert comments_url in gh.post_url
    assert labels_url in gh.post_url
    assert {"body": EMPTY_ISSUE_BODY_COMMENT} in gh.post_data
    assert {"labels": [Label.INVALID]} in gh.post_data
    assert issue_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_non_empty_issue_body():
    data = {
        "action": "opened",
        "issue": {
            "url": issue_url,
            "number": number,
            "comments_url": comments_url,
            "labels_url": labels_url,
            "user": {"login": user},
            "body": "There is one typo in test.py",
            "html_url": html_issue_url,
        },
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="issues", delivery_id="1")
    post = {comments_url: {}, labels_url: {}}
    patch = {issue_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    await issues.router.dispatch(event, gh)
    assert gh.getitem_url == []
    assert gh.getiter_url == []
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.patch_url == []
    assert gh.patch_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []
