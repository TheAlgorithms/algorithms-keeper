import pytest
from gidgethub.sansio import Event
from pytest import MonkeyPatch

from algorithms_keeper import utils
from algorithms_keeper.constants import Label
from algorithms_keeper.event.commands import COMMAND_RE, commands_router

from .test_parser import get_source
from .utils import (
    MockGitHubAPI,
    comment_url,
    files_url,
    html_pr_url,
    issue_url,
    labels_url,
    pr_url,
    reactions_url,
    review_url,
    sha,
    user,
)


@pytest.fixture(scope="module", autouse=True)
def patch_module(monkeypatch=MonkeyPatch()):
    async def mock_get_file_content(*args, **kwargs):
        filename = kwargs["file"].name
        if filename in {
            "doctest.py",
            "annotation.py",
            "descriptive_name.py",
            "return_annotation.py",
            "no_errors.py",
        }:
            return get_source(filename)
        else:
            return ""

    monkeypatch.setattr(utils, "get_file_content", mock_get_file_content)
    yield monkeypatch
    monkeypatch.undo()


@pytest.mark.parametrize(
    "text",
    (
        "algorithms-keeper test",
        "@algorithm-keeper test",
        "@algorithms_keeper test",
        "@algorithms-keepertest test",
        "@algorithms_keeper test-all",
    ),
)
def test_command_regex_no_match(text):
    assert COMMAND_RE.search(text) is None


@pytest.mark.parametrize(
    "text, group",
    (
        ("@algorithms-keeper test", "test"),
        ("@algorithms-keeper review", "review"),
        ("@algorithms-keeper      review     ", "review"),
        ("random @algorithms-keeper     review   random", "review"),
        ("@Algorithms-Keeper   REVIEW  ", "REVIEW"),
        ("@algorithms-keeper review-all", "review-all"),
        ("@algorithms-keeper     random-test   ", "random-test"),
    ),
)
def test_command_regex_match(text, group):
    assert COMMAND_RE.search(text).group(1) == group


@pytest.mark.asyncio
async def test_comment_by_non_member():
    data = {"action": "created", "comment": {"author_association": "NONE"}}
    event = Event(data, event="issue_comment", delivery_id="1")
    gh = MockGitHubAPI()
    await commands_router.dispatch(event, gh)
    assert not gh.post_url
    assert not gh.getitem_url
    assert not gh.delete_url


@pytest.mark.asyncio
async def test_comment_on_issue():
    data = {
        "action": "created",
        "comment": {
            "url": comment_url,
            "author_association": "MEMBER",
            "body": "@algorithms-keeper review",
        },
        "issue": {},
    }
    event = Event(data, event="issue_comment", delivery_id="1")
    post = {reactions_url: None}
    gh = MockGitHubAPI(post=post)
    await commands_router.dispatch(event, gh)
    assert len(gh.post_url) == 1
    assert reactions_url in gh.post_url
    assert {"content": "-1"} in gh.post_data
    assert not gh.getitem_url
    assert not gh.delete_url


@pytest.mark.asyncio
async def test_random_command():
    data = {
        "action": "created",
        "comment": {
            "author_association": "MEMBER",
            "body": "@algorithms-keeper random",
        },
    }
    event = Event(data, event="issue_comment", delivery_id="1")
    gh = MockGitHubAPI()
    await commands_router.dispatch(event, gh)
    assert not gh.post_url
    assert not gh.getitem_url
    assert not gh.getiter_url
    assert not gh.delete_url


@pytest.mark.asyncio
async def test_review_command():
    data = {
        "action": "created",
        "comment": {
            "url": comment_url,
            "author_association": "MEMBER",
            "body": "@algorithms-keeper review",
        },
        "issue": {"pull_request": {"url": pr_url}},
    }
    event = Event(data, event="issue_comment", delivery_id="1")
    post = {reactions_url: None}
    getitem = {
        pr_url: {
            "url": pr_url,
            "html_url": html_pr_url,
            "user": {"login": user},
            "labels": [],
            "draft": False,
        },
    }
    getiter = {files_url: []}
    gh = MockGitHubAPI(post=post, getitem=getitem, getiter=getiter)
    await commands_router.dispatch(event, gh)
    assert len(gh.post_url) == 1
    assert reactions_url in gh.post_url
    assert {"content": "+1"} in gh.post_data
    assert len(gh.getitem_url) == 1
    assert pr_url in gh.getitem_url
    assert len(gh.getiter_url) == 1
    assert files_url in gh.getiter_url
    assert not gh.delete_url


@pytest.mark.asyncio
async def test_review_all_command():
    data = {
        "action": "created",
        "comment": {
            "url": comment_url,
            "author_association": "MEMBER",
            "body": "@algorithms-keeper review-all",
        },
        "issue": {"pull_request": {"url": pr_url}},
    }
    event = Event(data, event="issue_comment", delivery_id="1")
    post = {reactions_url: None, labels_url: None, review_url: None}
    getitem = {
        pr_url: {
            "url": pr_url,
            "html_url": html_pr_url,
            "issue_url": issue_url,
            "head": {"sha": sha},
            "user": {"login": user},
            "labels": [],
            "draft": False,
        },
    }
    getiter = {
        files_url: [
            {"filename": "doctest.py", "contents_url": "", "status": "modified"},
        ]
    }
    gh = MockGitHubAPI(post=post, getitem=getitem, getiter=getiter)
    await commands_router.dispatch(event, gh)
    assert len(gh.post_url) == 3  # Two labels, one reaction
    assert reactions_url in gh.post_url
    assert labels_url in gh.post_url
    assert review_url not in gh.post_url
    assert {"labels": [Label.ENHANCEMENT]} in gh.post_data
    assert {"labels": [Label.REQUIRE_TEST]} in gh.post_data
    assert {"content": "+1"} in gh.post_data
    assert len(gh.getitem_url) == 1
    assert pr_url in gh.getitem_url
    assert len(gh.getiter_url) == 1
    assert files_url in gh.getiter_url
    assert not gh.delete_url
