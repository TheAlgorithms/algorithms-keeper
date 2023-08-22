from typing import Any, Generator
from urllib.parse import quote

import pytest
from gidgethub.sansio import Event

from algorithms_keeper import utils
from algorithms_keeper.constants import Label
from algorithms_keeper.event.pull_request import pull_request_router

from .test_parser import get_source
from .utils import (
    CHECKBOX_NOT_TICKED,
    CHECKBOX_TICKED,
    CHECKBOX_TICKED_UPPER,
    ExpectedData,
    MockGitHubAPI,
    check_run_url,
    comment,
    comments_url,
    files_url,
    html_pr_url,
    issue_url,
    labels_url,
    parametrize_id,
    pr_url,
    pr_user_search_url,
    repository,
    review_url,
    reviewers_url,
    sha,
    user,
)

# This constant can only contain one invalid filename.
INVALID = "invalid"

# There will be two items for this test to check on the only two possible cases:
# 1. MAX_PR_PER_USER = 1 (this should close the pull request)
# 2. MAX_PR_PER_USER = 0 (this should disable the check)
MAX_PR_TEST_NUMBER = 1
MAX_PR_TEST_ENABLED_ID = "max_pr_number_enabled"
MAX_PR_TEST_DISABLED_ID = "max_pr_number_disabled"
MAX_PR_TEST_ITEMS = [{"number": i} for i in range(1, MAX_PR_TEST_NUMBER + 2)]


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


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "event, gh, expected",
    # Pull request opened by the user, the bot found that the user has number of
    # open pull requests greater than ``MAX_PR_PER_USER`` constant, so close the
    # pull request with the appropriate comment.
    (
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED_UPPER,  # Case doesn't matter
                        "user": {"login": user, "type": "User"},
                        "labels": [],
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id=MAX_PR_TEST_ENABLED_ID,
            ),
            MockGitHubAPI(
                getiter={
                    pr_user_search_url: {
                        "total_count": len(MAX_PR_TEST_ITEMS),
                        "items": MAX_PR_TEST_ITEMS,
                    },
                    # Keeping this empty will allow us to test only what we want. This
                    # will be filled for the appropriate cases.
                    files_url: [],
                }
            ),
            ExpectedData(
                getiter_url=[pr_user_search_url],
                post_url=[comments_url, labels_url],
                post_data=[
                    {"labels": [Label.REVIEW]},
                    {"body": comment},
                ],
                patch_url=[pr_url],
                patch_data=[{"state": "closed"}],
                delete_url=[reviewers_url],
                delete_data=[{"reviewers": ["test1", "test2"]}],
            ),
        ),
        # Pull request opened by the user, the max pull request check is disabled, so do
        # not close the pull request.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED_UPPER,  # Case doesn't matter
                        "labels": [],
                        "user": {"login": user, "type": "User"},
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id=MAX_PR_TEST_DISABLED_ID,
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.REVIEW]}],
            ),
        ),
    ),
    ids=parametrize_id,
)
async def test_max_pr_by_user(
    monkeypatch: pytest.MonkeyPatch,
    event: Event,
    gh: MockGitHubAPI,
    expected: ExpectedData,
) -> None:
    # There are only two possible cases for the ``MAX_PR_BY_USER`` constant:
    # - The value is some arbitrary positive number greater than 0.
    # - The value is 0, which signals to disable the check.
    # We cannot rely on the actual constant which could change every now and then. So,
    # we will test the only two cases with monkeypatch.
    from algorithms_keeper.event import pull_request

    if event.delivery_id == MAX_PR_TEST_ENABLED_ID:
        monkeypatch.setattr(pull_request, "MAX_PR_PER_USER", MAX_PR_TEST_NUMBER)
    else:
        monkeypatch.setattr(pull_request, "MAX_PR_PER_USER", 0)
    await pull_request_router.dispatch(event, gh)
    assert gh == expected


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "event, gh, expected",
    (
        # Pull request opened with an empty body in non draft mode, so add
        # ``Label.REVIEW``, add ``Label.INVALID``, post the comment, close the pull
        # request and remove the requested reviewers, if any.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": "",
                        "user": {"login": user, "type": "User"},
                        "labels": [],
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="non_draft_empty_pr_body",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[labels_url, comments_url, labels_url],
                post_data=[
                    {"body": comment},
                    {"labels": [Label.INVALID]},
                    {"labels": [Label.REVIEW]},
                ],
                patch_url=[pr_url],
                patch_data=[{"state": "closed"}],
                delete_url=[reviewers_url],
                delete_data=[{"reviewers": ["test1", "test2"]}],
            ),
        ),
        # Pull request opened with an empty checklist in non draft mode, so add
        # ``Label.REVIEW``, add ``Label.INVALID``, post the comment, close the pull
        # request and remove the requested reviewers, if any.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_NOT_TICKED,
                        "user": {"login": user, "type": "User"},
                        "labels": [],
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="non_draft_empty_checklist",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[labels_url, comments_url, labels_url],
                post_data=[
                    {"body": comment},
                    {"labels": [Label.INVALID]},
                    {"labels": [Label.REVIEW]},
                ],
                patch_url=[pr_url],
                patch_data=[{"state": "closed"}],
                delete_url=[reviewers_url],
                delete_data=[{"reviewers": ["test1", "test2"]}],
            ),
        ),
        # Pull request opened with an empty body in draft mode, so add add
        # ``Label.INVALID``, post the comment, close the pull request and remove the
        # requested reviewers, if any.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": "",
                        "user": {"login": user, "type": "User"},
                        "labels": [],
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": True,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="draft_empty_pr_body",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[labels_url, comments_url],
                post_data=[
                    {"body": comment},
                    {"labels": [Label.INVALID]},
                ],
                patch_url=[pr_url],
                patch_data=[{"state": "closed"}],
                delete_url=[reviewers_url],
                delete_data=[{"reviewers": ["test1", "test2"]}],
            ),
        ),
        # Pull request opened, the parser found an invalid extension file, so the pull
        # request should be closed with the appropriate label and comment.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED,
                        "head": {"sha": sha},
                        "labels": [],
                        "user": {"login": user, "type": "User"},
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="invalid_extension_file",
            ),
            MockGitHubAPI(
                getiter={
                    pr_user_search_url: {"total_count": 1, "items": [{"number": 1}]},
                    files_url: [
                        {"filename": "file.py", "contents_url": "", "status": "added"},
                        {"filename": INVALID, "contents_url": "", "status": "added"},
                    ],
                }
            ),
            ExpectedData(
                getiter_url=[pr_user_search_url, files_url],
                post_url=[labels_url, labels_url, comments_url],
                post_data=[
                    {"labels": [Label.REVIEW]},
                    {"body": comment},
                    {"labels": [Label.INVALID]},
                ],
                patch_url=[pr_url],
                patch_data=[{"state": "closed"}],
                delete_url=[reviewers_url],
                delete_data=[{"reviewers": ["test1", "test2"]}],
            ),
        ),
        # ------------------------ ALL VALID PULL REQUESTS ------------------------
        # From this point onwards, all the pull requests are valid.
        # Pull request opened in draft mode, so only perform the validation checks.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED,
                        "user": {"login": user, "type": "User"},
                        "labels": [],
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": True,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="opened_in_draft_mode",
            ),
            MockGitHubAPI(
                getiter={
                    pr_user_search_url: {
                        "total_count": 1,
                        "items": [
                            {"number": 1, "state": "opened"},
                        ],
                    },
                }
            ),
            ExpectedData(getiter_url=[pr_user_search_url]),
        ),
        # Pull request synchronized while in draft mode, so do nothing.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED,
                        "user": {"login": user, "type": "User"},
                        "labels": [],
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": True,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="synchronize_in_draft_mode",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Pull request opened by a member of the organization, so don't perform
        # any validation checks. This will be checked by keeping the pull request body
        # empty for all test cases by member.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": "",  # body can be empty for member
                        "labels": [],
                        "user": {"login": user, "type": "User"},
                        "author_association": "MEMBER",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="pr_opened_by_member",
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.REVIEW]}],
            ),
        ),
        # Pull request opened by a bot, so don't perform any validation checks nor any
        # file checks. This will be verified by keeping the pull request body empty.
        (
            Event(
                data={
                    "action": "opened",
                    "pull_request": {
                        "url": pr_url,
                        "body": "",
                        "labels": [],
                        "user": {"login": "bot", "type": "Bot"},
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="pr_opened_by_bot",
            ),
            MockGitHubAPI(
                getiter={
                    files_url: [
                        {
                            "filename": "annotation.py",
                            "contents_url": "",
                            "status": "added",
                        },
                    ]
                }
            ),
            # No file checks should be performed by the bot. This is validated by
            # passing an invalid file in the mock data and no comment/label added
            # to the pull request.
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.REVIEW]}],
            ),
        ),
        # Pull request synchronized by a bot, so don't perform any file checks.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "labels": [{"name": Label.REVIEW}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "Bot"},
                },
                event="pull_request",
                delivery_id="pr_synchronized_by_bot",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Pull request synchronize event to test whether the add labels function gets
        # called if there are any labels to be added, post review comments gets called
        # if there are comments to be posted and remove labels function gets called if
        # there are labels to be removed.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED,
                        # This got added when the pull request was opened.
                        "labels": [{"name": Label.REVIEW}, {"name": Label.TYPE_HINT}],
                        "head": {"sha": sha},
                        "user": {"login": user, "type": "User"},
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="add_require_label",
            ),
            MockGitHubAPI(
                getiter={
                    files_url: [
                        {
                            "filename": "doctest.py",
                            "contents_url": "",
                            "status": "added",
                        },
                    ]
                }
            ),
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url, review_url],
                post_data=[
                    {"labels": [Label.REQUIRE_TEST]},
                    {"commit_id": sha, "event": "COMMENT"},
                ],
                delete_url=[f"{labels_url}/{quote(Label.TYPE_HINT)}"],
            ),
        ),
        # Pull request reopened and the files were checked, this test is mainly to check
        # whether the type label gets added to the pull request if the parser found it
        # of a specified type.
        (
            Event(
                data={
                    # Event action is reopened so as to test only the "type label" part.
                    "action": "reopened",
                    "pull_request": {
                        "url": pr_url,
                        # The label was added when the PR was opened.
                        "labels": [{"name": Label.REVIEW}],
                        "head": {"sha": sha},
                        "user": {"login": user, "type": "User"},
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="add_type_label",
            ),
            MockGitHubAPI(
                getiter={
                    files_url: [
                        {
                            "filename": "random.py",
                            "contents_url": "",
                            "status": "modified",
                        },
                    ]
                }
            ),
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.ENHANCEMENT]}],
            ),
        ),
        # Pull request made ready to be reviewed, thus add the ``Label.REVIEW`` label,
        # trigger the check for pull request files and also check the status of the
        # latest commit check runs and modify the labels accordingly.
        (
            Event(
                data={
                    "action": "ready_for_review",
                    "pull_request": {
                        "url": pr_url,
                        "body": CHECKBOX_TICKED,
                        "head": {"sha": sha},
                        "labels": [],
                        "user": {"login": user, "type": "User"},
                        "author_association": "NONE",
                        "comments_url": comments_url,
                        "issue_url": issue_url,
                        "html_url": html_pr_url,
                        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "repository": {"full_name": repository},
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="label_on_ready_for_review",
            ),
            MockGitHubAPI(
                getitem={
                    check_run_url: {
                        "total_count": 2,
                        "check_runs": [
                            {"status": "completed", "conclusion": "success"},
                            {"status": "completed", "conclusion": "failure"},
                        ],
                    },
                },
                getiter={files_url: []},
            ),
            ExpectedData(
                getitem_url=[check_run_url],
                getiter_url=[files_url],
                post_url=[labels_url, labels_url],
                post_data=[{"labels": [Label.FAILED_TEST]}, {"labels": [Label.REVIEW]}],
            ),
        ),
        # Pull request review commented by a non-member. We ignore all pull request
        # review comments, so no action should be taken.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "commented",
                        "author_association": "NONE",
                    },
                    "pull_request": {},
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="review_comment_by_non_member",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Pull request review commented by a member. We ignore all pull request
        # review comments, so no action should be taken.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "commented",
                        "author_association": "MEMBER",
                    },
                    "pull_request": {},
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="review_comment_by_member",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Pull request review changes requested by a non-member, as it is by a
        # non-member, no action should be taken.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "changes_requested",
                        "author_association": "NONE",
                    },
                    "pull_request": {},
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="changes_requested_by_non_member",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Pull request review changes requested by a member, so modify the labels.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "changes_requested",
                        "author_association": "MEMBER",
                    },
                    "pull_request": {
                        "labels": [],
                        "issue_url": issue_url,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="changes_requested_by_member_no_label",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[labels_url],
                post_data=[{"labels": [Label.CHANGE]}],
            ),
        ),
        # Now we have checked the case where review comments were made by non-member,
        # all subsequent actions for the review comments will be done by a member.
        # Pull request review changes requested with label already present.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "changes_requested",
                        "author_association": "MEMBER",
                    },
                    "pull_request": {
                        "labels": [{"name": Label.CHANGE}],
                        "issue_url": issue_url,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="changes_requested_with_change_label",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Pull request review requested changes with ``Label.CHANGE`` present, so remove
        # the change label and add the ``Label.REVIEW`` label.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "changes_requested",
                        "author_association": "MEMBER",
                    },
                    "pull_request": {
                        "labels": [{"name": Label.REVIEW}],
                        "issue_url": issue_url,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="changes_requested_with_review_label",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[labels_url],
                post_data=[{"labels": [Label.CHANGE]}],
                delete_url=[f"{labels_url}/{quote(Label.REVIEW)}"],
            ),
        ),
        # Pull request approved with review label on it, so remove the label.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "approved",
                        "author_association": "MEMBER",
                    },
                    "pull_request": {
                        "labels": [{"name": Label.REVIEW}],
                        "issue_url": issue_url,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="approved_with_review_label",
            ),
            MockGitHubAPI(),
            ExpectedData(delete_url=[f"{labels_url}/{quote(Label.REVIEW)}"]),
        ),
        # Pull request approved with change label on it, so remove the label.
        (
            Event(
                data={
                    "action": "submitted",
                    "review": {
                        "state": "approved",
                        "author_association": "MEMBER",
                    },
                    "pull_request": {
                        "labels": [{"name": Label.CHANGE}],
                        "issue_url": issue_url,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request_review",
                delivery_id="approved_with_change_label",
            ),
            MockGitHubAPI(),
            ExpectedData(delete_url=[f"{labels_url}/{quote(Label.CHANGE)}"]),
        ),
        # No labels to add and remove while in draft mode.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [{"name": Label.CHANGE}],
                        "draft": True,
                        "mergeable": True,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="no_label_in_draft_mode",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
        # Add the review label after the author made the necessary changes.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [{"name": Label.CHANGE}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="review_label_after_changes_made",
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.REVIEW]}],
                delete_url=[f"{labels_url}/{quote(Label.CHANGE)}"],
            ),
        ),
        # Remove all the awaiting labels after the pull request is merged, if any.
        (
            Event(
                data={
                    "action": "closed",
                    "pull_request": {
                        "merged": True,
                        "issue_url": issue_url,
                        "labels": [{"name": Label.REVIEW}],
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="remove_labels_on_pr_closed",
            ),
            MockGitHubAPI(),
            ExpectedData(delete_url=[f"{labels_url}/{quote(Label.REVIEW)}"]),
        ),
        # Remove all the awaiting labels after the pull request is closed and not merged
        # as it was considered to be invalid.
        (
            Event(
                data={
                    "action": "closed",
                    "pull_request": {
                        "merged": False,
                        "issue_url": issue_url,
                        "labels": [{"name": Label.REVIEW}, {"name": Label.INVALID}],
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="remove_labels_on_invalid_pr_closed",
            ),
            MockGitHubAPI(),
            ExpectedData(delete_url=[f"{labels_url}/{quote(Label.REVIEW)}"]),
        ),
        # Check whether the poll is being made if the mergeable value is ``None``.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [{"name": Label.REVIEW}],
                        "draft": False,
                        "mergeable": None,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="mergeable_value_is_none",
            ),
            MockGitHubAPI(
                getiter={files_url: []},
                getitem={
                    pr_url: {
                        "url": pr_url,
                        "labels": [],
                        "mergeable": True,
                    }
                },
            ),
            ExpectedData(
                getiter_url=[files_url],
                getitem_url=[pr_url],
            ),
        ),
        # The pull request has no merge conflicts and the label does not exist, so do
        # not take any action.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [{"name": Label.REVIEW}],
                        "draft": False,
                        "mergeable": True,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="mergeable_value_is_true_no_label",
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(getiter_url=[files_url]),
        ),
        # The pull request has no merge conflicts and the label exist, so remove the
        # label.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [
                            {"name": Label.REVIEW},
                            {"name": Label.MERGE_CONFLICT},
                        ],
                        "draft": False,
                        "mergeable": True,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="mergeable_value_is_true_with_label",
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(
                getiter_url=[files_url],
                delete_url=[f"{labels_url}/{quote(Label.MERGE_CONFLICT)}"],
            ),
        ),
        # The pull request contains merge conflicts and the label does not exist, so
        # add the label.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [{"name": Label.REVIEW}],
                        "draft": False,
                        "mergeable": False,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="mergeable_value_is_false_no_label",
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(
                getiter_url=[files_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.MERGE_CONFLICT]}],
            ),
        ),
        # The pull request contains merge conflicts and the label exists as well, so
        # do not take any action.
        (
            Event(
                data={
                    "action": "synchronize",
                    "pull_request": {
                        "url": pr_url,
                        "html_url": html_pr_url,
                        "user": {"login": user, "type": "User"},
                        "issue_url": issue_url,
                        "labels": [
                            {"name": Label.REVIEW},
                            {"name": Label.MERGE_CONFLICT},
                        ],
                        "draft": False,
                        "mergeable": False,
                    },
                    "sender": {"type": "User"},
                },
                event="pull_request",
                delivery_id="mergeable_value_is_false_with_label",
            ),
            MockGitHubAPI(getiter={files_url: []}),
            ExpectedData(getiter_url=[files_url]),
        ),
    ),
    ids=parametrize_id,
)
async def test_pull_request(
    event: Event, gh: MockGitHubAPI, expected: ExpectedData
) -> None:
    await pull_request_router.dispatch(event, gh)
    assert gh == expected
