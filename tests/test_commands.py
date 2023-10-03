from typing import Any, Generator

import pytest
from gidgethub.sansio import Event

from algorithms_keeper import utils
from algorithms_keeper.constants import Label
from algorithms_keeper.event.commands import COMMAND_RE, commands_router

from .test_parser import get_source
from .utils import (
    ExpectedData,
    MockGitHubAPI,
    comment,
    comment_url,
    comments_url,
    files_url,
    html_pr_url,
    issue_url,
    labels_url,
    parametrize_id,
    pr_url,
    reactions_url,
    sha,
    user,
)


@pytest.fixture(scope="module", autouse=True)
def patch_module(
    monkeypatch: pytest.MonkeyPatch = pytest.MonkeyPatch(),
) -> Generator[pytest.MonkeyPatch, None, None]:
    async def mock_get_file_content(*args: Any, **kwargs: Any) -> bytes:
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
            return b""

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
def test_command_regex_no_match(text: str) -> None:
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
def test_command_regex_match(text: str, group: str) -> None:
    match = COMMAND_RE.search(text)
    assert match is not None
    assert match.group(1) == group


# Reminder: ``Event.delivery_id`` is used as a short description for the respective
# test case and as a way to id the specific test case in the parametrized group.
@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "event, gh, expected",
    (
        # Issue comment made by a non member, so do nothing.
        (
            Event(
                data={
                    "action": "created",
                    "comment": {
                        "author_association": "NONE",
                    },
                },
                event="issue_comment",
                delivery_id="non_member_commented",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Issue comment came from an issue instead of a pull request, so do nothing.
        (
            Event(
                data={
                    "action": "created",
                    "comment": {
                        "url": comment_url,
                        "author_association": "MEMBER",
                        "body": "@algorithms-keeper review",
                    },
                    "issue": {},
                },
                event="issue_comment",
                delivery_id="comment_came_from_issue",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[reactions_url],
                post_data=[{"content": "-1"}],
            ),
        ),
        # Issue comment parsed and command was extracted, the command is not
        # programmed, so do nothing.
        (
            Event(
                data={
                    "action": "created",
                    "comment": {
                        "author_association": "MEMBER",
                        "body": "@algorithms-keeper random",
                    },
                },
                event="issue_comment",
                delivery_id="random_command",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Issue comment parsed and command was extracted, the command is `review`,
        # post a reaction, get the pull request data and pass it onto the
        # ``event.pull_request.check_pr_files`` function.
        (
            Event(
                data={
                    "action": "created",
                    "comment": {
                        "url": comment_url,
                        "author_association": "MEMBER",
                        "body": "@algorithms-keeper review",
                    },
                    "issue": {
                        "pull_request": {
                            "url": pr_url,
                        }
                    },
                },
                event="issue_comment",
                delivery_id="review_command",
            ),
            MockGitHubAPI(
                getitem={
                    pr_url: {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "author_association": "MEMBER",
                        "labels": [],
                        "draft": False,
                    },
                },
                getiter={files_url: []},
            ),
            ExpectedData(
                post_url=[reactions_url],
                post_data=[{"content": "+1"}],
                getitem_url=[pr_url],
                getiter_url=[files_url],
            ),
        ),
        # Issue comment parsed and command was extracted, the command is `review-all`,
        # post a reaction, get the pull request data and pass it onto the
        # ``event.pull_request.check_pr_files`` function.
        (
            Event(
                data={
                    "action": "created",
                    "comment": {
                        "url": comment_url,
                        "author_association": "MEMBER",
                        "body": "@algorithms-keeper review-all",
                    },
                    "issue": {
                        "pull_request": {
                            "url": pr_url,
                        }
                    },
                },
                event="issue_comment",
                delivery_id="review_all_command",
            ),
            MockGitHubAPI(
                getitem={
                    pr_url: {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "issue_url": issue_url,
                        "head": {"sha": sha},
                        "user": {"login": user, "type": "User"},
                        "author_association": "MEMBER",
                        "comments_url": comments_url,
                        "labels": [],
                        "draft": False,
                    },
                },
                getiter={
                    files_url: [
                        {
                            "filename": "descriptive_name.py",
                            "contents_url": "",
                            "status": "modified",
                        },
                    ]
                },
            ),
            ExpectedData(
                post_url=[reactions_url, labels_url, labels_url, comments_url],
                post_data=[
                    {"labels": [Label.ENHANCEMENT]},
                    {"labels": [Label.DESCRIPTIVE_NAME]},
                    {"content": "+1"},
                    {"body": comment},
                ],
                getitem_url=[pr_url],
                getiter_url=[files_url],
            ),
        ),
    ),
    ids=parametrize_id,
)
async def test_command(event: Event, gh: MockGitHubAPI, expected: ExpectedData) -> None:
    await commands_router.dispatch(event, gh)
    assert gh == expected
