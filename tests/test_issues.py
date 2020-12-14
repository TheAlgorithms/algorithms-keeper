import pytest
from gidgethub import sansio

from algorithms_keeper.constants import EMPTY_ISSUE_BODY_COMMENT, Label
from algorithms_keeper.event.issues import issues_router

from .utils import (
    MockGitHubAPI,
    comments_url,
    html_issue_url,
    issue_url,
    labels_url,
    number,
    user,
)

EMPTY_ISSUE_BODY_COMMENT = EMPTY_ISSUE_BODY_COMMENT.format(user_login=user)


@pytest.mark.asyncio
async def test_empty_issue_body():
    data = {
        "action": "opened",
        "issue": {
            "url": issue_url,
            "comments_url": comments_url,
            "labels_url": labels_url,
            "user": {"login": user},
            "body": "",
            "html_url": html_issue_url,
        },
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="issues", delivery_id="1")
    post = {comments_url: {}, labels_url: {}}
    patch = {issue_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    await issues_router.dispatch(event, gh)
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
            "comments_url": comments_url,
            "labels_url": labels_url,
            "user": {"login": user},
            "body": "There is one typo in test.py",
            "html_url": html_issue_url,
        },
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="issues", delivery_id="1")
    post = {comments_url: {}, labels_url: {}}
    patch = {issue_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    await issues_router.dispatch(event, gh)
    assert gh.getitem_url == []
    assert gh.getiter_url == []
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.patch_url == []
    assert gh.patch_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []
