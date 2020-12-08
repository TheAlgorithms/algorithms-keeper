import urllib.parse

import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import sansio

from algorithms_keeper import pull_requests, utils
from algorithms_keeper.constants import (
    CHECKBOX_NOT_TICKED_COMMENT,
    EMPTY_BODY_COMMENT,
    INVALID_EXTENSION_COMMENT,
    MAX_PR_REACHED_COMMENT,
    Label,
)

from .test_parser import get_source
from .utils import (
    CHECKBOX_NOT_TICKED,
    CHECKBOX_TICKED,
    CHECKBOX_TICKED_UPPER,
    MockGitHubAPI,
    check_run_url,
    comments_url,
    files_url,
    html_pr_url,
    issue_url,
    labels_url,
    pr_url,
    pr_user_search_url,
    repository,
    review_url,
    reviewers_url,
    sha,
    user,
)

# Comment constants
EMPTY_BODY_COMMENT = EMPTY_BODY_COMMENT.format(user_login=user)
CHECKBOX_NOT_TICKED_COMMENT = CHECKBOX_NOT_TICKED_COMMENT.format(user_login=user)


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body, comment, draft",
    (
        # Empty body, non-draft PR
        ("", EMPTY_BODY_COMMENT, False),
        # Checklist empty, non-draft PR
        (CHECKBOX_NOT_TICKED, CHECKBOX_NOT_TICKED_COMMENT, False),
        # Empty body, draft PR
        ("", EMPTY_BODY_COMMENT, True),
    ),
)
async def test_invalid_pr_opened(body, comment, draft):
    data = {
        "action": "opened",
        "pull_request": {
            "url": pr_url,
            "body": body,
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
            "draft": draft,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None, comments_url: None}
    patch = {pr_url: None}
    delete = {reviewers_url: None}
    gh = MockGitHubAPI(post=post, patch=patch, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert len(gh.post_url) == 2
    assert comments_url in gh.post_url
    assert labels_url in gh.post_url
    assert {"body": comment} in gh.post_data
    assert {"labels": [Label.INVALID]} in gh.post_data
    assert pr_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert reviewers_url in gh.delete_url
    assert {"reviewers": ["test1", "test2"]} in gh.delete_data


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ("opened", "synchronize"))
async def test_pr_opened_synchronize_in_draft_mode(action):
    # Draft PR opened
    # Draft PR synchronize
    data = {
        "action": action,
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "user": {"login": user},
            "labels": [],
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
            "draft": True,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {
        pr_user_search_url: {
            "total_count": 1,
            "items": [
                {"number": 1, "state": "opened"},
            ],
        },
    }
    gh = MockGitHubAPI(getiter=getiter)
    await pull_requests.router.dispatch(event, gh)
    if action == "opened":
        assert pr_user_search_url in gh.getiter_url
    else:
        assert not gh.getiter_url
    assert not gh.post_url
    assert not gh.post_data
    assert not gh.patch_url
    assert not gh.patch_data
    assert not gh.delete_url
    assert not gh.delete_data


@pytest.mark.asyncio
async def test_pr_opened_by_member():
    data = {
        "action": "opened",
        "pull_request": {
            "url": pr_url,
            "body": "",  # body can be empty for member
            "labels": [],
            "user": {"login": user},
            "author_association": "MEMBER",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None}
    getiter = {files_url: []}  # for check_pr_files function
    gh = MockGitHubAPI(getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    assert files_url in gh.getiter_url
    assert labels_url in gh.post_url
    assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data


@pytest.mark.asyncio
async def test_max_pr_reached():
    data = {
        "action": "opened",
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED_UPPER,  # Case doesn't matter
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    # We don't want to fix the tests on a specific MAX_PR_PER_USER count.
    items = [{"number": i} for i in range(1, pull_requests.MAX_PR_PER_USER + 2)]
    getiter = {
        pr_user_search_url: {"total_count": len(items), "items": items},
        files_url: [],  # for check_pr_files function
    }
    post = {comments_url: None}
    patch = {pr_url: None}
    delete = {reviewers_url: None}
    gh = MockGitHubAPI(getiter=getiter, post=post, patch=patch, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert pr_user_search_url in gh.getiter_url
    assert comments_url in gh.post_url
    assert {
        "body": MAX_PR_REACHED_COMMENT.format(user_login=user, pr_number="#1, #2")
    } in gh.post_data
    assert pr_url in gh.patch_url
    assert reviewers_url in gh.delete_url
    assert {"reviewers": ["test1", "test2"]} in gh.delete_data


@pytest.mark.asyncio
async def test_max_pr_disabled(monkeypatch):
    monkeypatch.setattr(pull_requests, "MAX_PR_PER_USER", 0)
    data = {
        "action": "opened",
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED_UPPER,  # Case doesn't matter
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None}
    getiter = {files_url: []}
    gh = MockGitHubAPI(getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    assert files_url in gh.getiter_url
    # No changes as max pr checks are disabled
    assert labels_url in gh.post_url
    assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data


@pytest.mark.asyncio
async def test_for_extensionless_files():
    # PRs containing extensionless files will be closed, so no point in checking for
    # synchronize action.
    data = {
        "action": "opened",
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "head": {"sha": sha},
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")

    getiter = {
        pr_user_search_url: {"total_count": 1, "items": [{"number": 1}]},
        files_url: [
            {"filename": "newton.py", "contents_url": "", "status": "added"},
            {"filename": "fibonacci", "contents_url": "", "status": "added"},
        ],
    }
    post = {comments_url: None, labels_url: None}
    patch = {pr_url: None}
    delete = {reviewers_url: None}
    gh = MockGitHubAPI(getiter=getiter, post=post, patch=patch, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert len(gh.getiter_url) == 2
    assert pr_user_search_url in gh.getiter_url
    assert files_url in gh.getiter_url
    assert len(gh.post_url) == 3  # Two labels and one comment.
    assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data
    assert comments_url in gh.post_url
    assert labels_url in gh.post_url
    assert {
        "body": INVALID_EXTENSION_COMMENT.format(user_login=user, files="fibonacci")
    } in gh.post_data
    assert {"labels": [Label.INVALID]} in gh.post_data
    assert pr_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert reviewers_url in gh.delete_url
    assert {"reviewers": ["test1", "test2"]} in gh.delete_data


@pytest.mark.asyncio
async def test_pr_with_no_python_files():
    # Opened event are checked, thus we will use 'synchronize' to not trigger the
    # 'close_invalid_pr' function.
    data = {
        "action": "synchronize",
        "pull_request": {
            "url": pr_url,
            # The label was added when the PR was opened.
            "labels": [{"name": Label.AWAITING_REVIEW}],
            "head": {"sha": sha},
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {
        files_url: [
            {"filename": ".travis.yml", "contents_url": "", "status": "added"},
            {"filename": "README.md", "contents_url": "", "status": "added"},
            # We will add one `__` Python file in the mix which should be
            # ignored.
            {"filename": "__init__.py", "contents_url": "", "status": "added"},
        ],
    }
    post = {labels_url: None}
    gh = MockGitHubAPI(getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    assert len(gh.getiter_url) == 1
    assert files_url in gh.getiter_url
    assert not gh.post_url
    assert not gh.post_data
    # Nothing happens as there are no Python files
    assert not gh.patch_url
    assert not gh.patch_data
    assert not gh.delete_url
    assert not gh.delete_data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, getiter",
    (
        (
            "opened",
            {
                pr_user_search_url: {"total_count": 1, "items": [{"number": 1}]},
                files_url: [
                    {
                        "filename": "doctest.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {"filename": "test_algo.py", "contents_url": "", "status": "added"},
                    {
                        "filename": "annotation.py",
                        "contents_url": "",
                        "status": "added",
                    },
                ],
            },
        ),
        (
            "synchronize",
            {
                files_url: [
                    {
                        "filename": "doctest.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {"filename": "test_algo.py", "contents_url": "", "status": "added"},
                    {
                        "filename": "annotation.py",
                        "contents_url": "",
                        "status": "added",
                    },
                ],
            },
        ),
    ),
)
async def test_pr_with_test_file(action, getiter):
    remove_label = urllib.parse.quote(Label.REQUIRE_TEST)
    data = {
        "action": action,
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            # This is like a marker to test the function, the label should be removed.
            "labels": [{"name": Label.REQUIRE_TEST}],
            "head": {"sha": sha},
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None, review_url: None}
    delete = {f"{labels_url}/{remove_label}": None}
    gh = MockGitHubAPI(getiter=getiter, post=post, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    if data["action"] == "opened":
        assert len(gh.getiter_url) == 2
        assert pr_user_search_url in gh.getiter_url
        assert files_url in gh.getiter_url
        assert len(gh.post_url) == 3  # Two labels and one comment.
        assert review_url in gh.post_url
        assert labels_url in gh.post_url
        assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data
    elif data["action"] == "synchronize":
        assert len(gh.getiter_url) == 1
        assert files_url in gh.getiter_url
        assert len(gh.post_url) == 2
        assert review_url in gh.post_url
        assert labels_url in gh.post_url
    assert {"labels": [Label.ANNOTATIONS]} in gh.post_data
    assert gh.delete_url[0] == f"{labels_url}/{remove_label}"
    assert not gh.delete_data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, getiter",
    (
        (
            "opened",
            {
                pr_user_search_url: {"total_count": 1, "items": [{"number": 1}]},
                files_url: [
                    {"filename": "no_errors.py", "contents_url": "", "status": "added"},
                    {"filename": "algorithm.py", "contents_url": "", "status": "added"},
                ],
            },
        ),
        (
            "synchronize",
            {
                files_url: [
                    {"filename": "no_errors.py", "contents_url": "", "status": "added"},
                    {"filename": "algorithm.py", "contents_url": "", "status": "added"},
                ],
            },
        ),
    ),
)
async def test_pr_with_successful_tests(action, getiter):
    data = {
        "action": action,
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [],
            "head": {"sha": sha},
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None}
    gh = MockGitHubAPI(getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    if data["action"] == "opened":
        assert len(gh.getiter_url) == 2
        assert gh.getiter_url == [pr_user_search_url, files_url]
        assert labels_url in gh.post_url
        assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data
    elif data["action"] == "synchronize":
        assert len(gh.getiter_url) == 1
        assert gh.getiter_url[0] == files_url


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, getiter",
    (
        (
            "opened",
            {
                pr_user_search_url: {"total_count": 1, "items": [{"number": 1}]},
                files_url: [
                    {
                        "filename": "doctest.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {
                        "filename": "descriptive_name.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {
                        "filename": "annotation.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {
                        "filename": "return_annotation.py",
                        "contents_url": "",
                        "status": "added",
                    },
                ],
            },
        ),
        (
            "synchronize",
            {
                files_url: [
                    {
                        "filename": "doctest.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {
                        "filename": "descriptive_name.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {
                        "filename": "annotation.py",
                        "contents_url": "",
                        "status": "added",
                    },
                    {
                        "filename": "return_annotation.py",
                        "contents_url": "",
                        "status": "added",
                    },
                ],
            },
        ),
    ),
)
async def test_pr_with_add_all_require_labels(action, getiter):
    data = {
        "action": action,
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [],
            "head": {"sha": sha},
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None, review_url: None}
    gh = MockGitHubAPI(getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    if data["action"] == "opened":
        assert len(gh.getiter_url) == 2
        assert pr_user_search_url in gh.getiter_url
        assert files_url in gh.getiter_url
        assert len(gh.post_url) == 3
        assert labels_url in gh.post_url
        assert review_url in gh.post_url
        assert {"labels": [Label.AWAITING_REVIEW]}
    elif data["action"] == "synchronize":
        assert len(gh.getiter_url) == 1
        assert files_url in gh.getiter_url
        assert len(gh.post_url) == 3
        assert review_url in gh.post_url
        assert comments_url not in gh.post_url
        assert labels_url in gh.post_url
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_with_remove_all_require_labels():
    # This case will only be true when the action is `synchronize`
    test_label_url = labels_url + f"/{urllib.parse.quote(Label.REQUIRE_TEST)}"
    names_label_url = labels_url + f"/{urllib.parse.quote(Label.DESCRIPTIVE_NAMES)}"
    annotation_label_url = labels_url + f"/{urllib.parse.quote(Label.ANNOTATIONS)}"
    data = {
        "action": "synchronize",
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [
                {"name": Label.REQUIRE_TEST},
                {"name": Label.DESCRIPTIVE_NAMES},
                {"name": Label.ANNOTATIONS},
            ],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {
        files_url: [
            {"filename": "no_errors.py", "contents_url": "", "status": "added"},
            {"filename": "algorithm.py", "contents_url": "", "status": "added"},
        ],
    }
    delete = {test_label_url: None, names_label_url: None, annotation_label_url: None}
    gh = MockGitHubAPI(getiter=getiter, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert len(gh.getiter_url) == 1
    assert files_url in gh.getiter_url
    # No labels are added
    assert gh.post_url == []
    assert gh.post_data == []
    # All labels are deleted
    assert test_label_url in gh.delete_url
    assert names_label_url in gh.delete_url
    assert annotation_label_url in gh.delete_url
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_add_type_label_on_pr():
    # Event action is reopened so as to test only the "type label" part.
    data = {
        "action": "reopened",
        "pull_request": {
            "url": pr_url,
            # The label was added when the PR was opened.
            "labels": [{"name": Label.AWAITING_REVIEW}],
            "head": {"sha": sha},
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {
        files_url: [
            {"filename": "no_errors.py", "contents_url": "", "status": "modified"},
        ]
    }
    post = {labels_url: None}
    gh = MockGitHubAPI(getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    assert len(gh.getiter_url) == 1
    assert files_url in gh.getiter_url
    assert labels_url in gh.post_url
    assert {"labels": [Label.ENHANCEMENT]} in gh.post_data


@pytest.mark.asyncio
async def test_label_on_ready_for_review_pr():
    # Open a PR in draft
    # Convert the draft PR to ready for review PR
    # Tests are failing on the latest commit, so test that it adds the label
    data = {
        "action": "ready_for_review",
        "pull_request": {
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "head": {"sha": sha},
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
            "draft": False,
        },
        "repository": {"full_name": repository},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getitem = {
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "failure"},
            ],
        },
    }
    getiter = {files_url: []}
    post = {labels_url: None}
    gh = MockGitHubAPI(getitem=getitem, getiter=getiter, post=post)
    await pull_requests.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 1
    assert check_run_url in gh.getitem_url
    assert len(gh.getiter_url) == 1
    assert files_url in gh.getiter_url
    assert labels_url in gh.post_url
    assert {"labels": [Label.FAILED_TEST]} in gh.post_data


@pytest.mark.parametrize("state", ("commented", "changes_requested", "approved"))
async def test_pr_review_by_non_member(state):
    data = {
        "action": "submitted",
        "review": {
            "state": state,
            "author_association": "NONE",
        },
        "pull_request": {},
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    gh = MockGitHubAPI()
    await pull_requests.router.dispatch(event, gh)
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_review_changes_requested_no_label():
    data = {
        "action": "submitted",
        "review": {
            "state": "changes_requested",
            "author_association": "MEMBER",
        },
        "pull_request": {
            "labels": [],
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    post = {labels_url: None}
    gh = MockGitHubAPI(post=post)
    await pull_requests.router.dispatch(event, gh)
    assert labels_url in gh.post_url
    assert {"labels": [Label.CHANGES_REQUESTED]} in gh.post_data
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_review_changes_requested_with_label():
    data = {
        "action": "submitted",
        "review": {
            "state": "changes_requested",
            "author_association": "MEMBER",
        },
        "pull_request": {
            "labels": [{"name": Label.CHANGES_REQUESTED}],
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    post = {labels_url: None}
    gh = MockGitHubAPI(post=post)
    await pull_requests.router.dispatch(event, gh)
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_review_changes_requested_with_review_label():
    remove_label = urllib.parse.quote(Label.AWAITING_REVIEW)
    data = {
        "action": "submitted",
        "review": {
            "state": "changes_requested",
            "author_association": "MEMBER",
        },
        "pull_request": {
            "labels": [{"name": Label.AWAITING_REVIEW}],
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    post = {labels_url: None}
    delete = {f"{labels_url}/{remove_label}": None}
    gh = MockGitHubAPI(post=post, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert labels_url in gh.post_url
    assert {"labels": [Label.CHANGES_REQUESTED]} in gh.post_data
    assert f"{labels_url}/{remove_label}" in gh.delete_url
    assert gh.delete_data == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "labels", ([{"name": Label.AWAITING_REVIEW}], [{"name": Label.CHANGES_REQUESTED}])
)
async def test_pr_approved_with_label(labels):
    remove_label = urllib.parse.quote(labels[0]["name"])
    data = {
        "action": "submitted",
        "review": {
            "state": "approved",
            "author_association": "MEMBER",
        },
        "pull_request": {
            "labels": labels,
            "issue_url": issue_url,
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    delete = {f"{labels_url}/{remove_label}": None}
    gh = MockGitHubAPI(delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert f"{labels_url}/{remove_label}" in gh.delete_url
    assert gh.delete_data == []
    assert gh.post_url == []
    assert gh.post_data == []


# Test conditions for when to add and remove `Label.AWAITING_REVIEW` label:
# NOTE: All conditions assumes the PR has been already been labeled AWAITING_REVIEW when
#       it was opened.
# 1. PR opened with no errors (No error labels were added)
# 2. PR opened with errors (Error labels were added)
# 3. One or more label from PR_NOT_READY_LABELS were removed but not all
# 4. All labels from PR present in PR_NOT_READY_LABELS were removed
# 5. CHANGES_REQUESTED label was added (PR was reviewed)
# 6. CHANGES_REQUESTED label was removed (PR was approved)


@pytest.mark.asyncio
async def test_pr_opened_with_no_errors_and_labeled():
    data = {
        "action": "labeled",
        "pull_request": {
            "labels": [{"name": Label.AWAITING_REVIEW}],
            "issue_url": issue_url,
        },
        "label": {"name": Label.AWAITING_REVIEW},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = MockGitHubAPI()
    await pull_requests.router.dispatch(event, gh)
    # No label is added or removed.
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_opened_with_errors_and_labeled():
    remove_label = urllib.parse.quote(Label.AWAITING_REVIEW)
    data = {
        "action": "labeled",
        "pull_request": {
            "labels": [{"name": Label.AWAITING_REVIEW}, {"name": Label.REQUIRE_TEST}],
            "issue_url": issue_url,
        },
        "label": {"name": Label.REQUIRE_TEST},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    delete = {f"{labels_url}/{remove_label}": None}
    gh = MockGitHubAPI(delete=delete)
    await pull_requests.router.dispatch(event, gh)
    # No labels were added.
    assert gh.post_url == []
    assert gh.post_data == []
    # AWAITING_REVIEW label was removed.
    assert f"{labels_url}/{remove_label}" in gh.delete_url
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_not_all_labels_removed():
    data = {
        "action": "unlabeled",
        "pull_request": {
            "labels": [{"name": Label.REQUIRE_TEST}],
            "issue_url": issue_url,
        },
        "label": {"name": Label.ANNOTATIONS},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = MockGitHubAPI()
    await pull_requests.router.dispatch(event, gh)
    # No label is added or removed.
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_pr_all_labels_removed():
    data = {
        "action": "unlabeled",
        "pull_request": {
            "labels": [{"name": "good first issue"}],  # Random label.
            "issue_url": issue_url,
        },
        "label": {"name": Label.ANNOTATIONS},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: None}
    gh = MockGitHubAPI(post=post)
    await pull_requests.router.dispatch(event, gh)
    # No error labels so the AWAITING_REVIEW label should be added.
    assert labels_url in gh.post_url
    assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
@pytest.mark.parametrize("labels", ([{"name": Label.CHANGES_REQUESTED}], []))
async def test_changes_requested_label_added_and_removed(labels):
    data = {
        "action": "labeled",
        "pull_request": {
            "labels": labels,
            "issue_url": issue_url,
        },
        "label": {"name": Label.CHANGES_REQUESTED},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = MockGitHubAPI()
    await pull_requests.router.dispatch(event, gh)
    assert gh.delete_url == []
    assert gh.delete_data == []
    assert gh.post_url == []
    assert gh.post_data == []


@pytest.mark.asyncio
async def test_awaiting_review_label_removed():
    # Issue #10
    data = {
        "action": "unlabeled",
        "pull_request": {
            "labels": [],
            "issue_url": issue_url,
        },
        "label": {"name": Label.AWAITING_REVIEW},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = MockGitHubAPI()
    await pull_requests.router.dispatch(event, gh)
    # No label is added or removed.
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_no_label_in_draft_mode():
    data = {
        "action": "synchronize",
        "pull_request": {
            "user": {"login": user},
            "issue_url": issue_url,
            "labels": [{"name": Label.CHANGES_REQUESTED}],
            "draft": True,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = MockGitHubAPI()
    await pull_requests.router.dispatch(event, gh)
    assert gh.delete_url == []
    assert gh.delete_data == []
    assert gh.post_url == []
    assert gh.post_data == []


@pytest.mark.asyncio
async def test_no_review_label_when_pr_not_ready():
    remove_label = urllib.parse.quote(Label.ANNOTATIONS)
    data = {
        "action": "synchronize",
        "pull_request": {
            "url": pr_url,
            "user": {"login": user},
            "issue_url": issue_url,
            "labels": [{"name": Label.ANNOTATIONS}],
            "draft": False,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {files_url: []}
    delete = {f"{labels_url}/{remove_label}": None}
    gh = MockGitHubAPI(getiter=getiter, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert gh.post_url == []
    assert gh.post_data == []


@pytest.mark.asyncio
async def test_review_label_after_changes_made():
    remove_label = urllib.parse.quote(Label.CHANGES_REQUESTED)
    data = {
        "action": "synchronize",
        "pull_request": {
            "url": pr_url,
            "user": {"login": user},
            "issue_url": issue_url,
            "labels": [{"name": Label.CHANGES_REQUESTED}],
            "draft": False,
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    delete = {f"{labels_url}/{remove_label}": None}
    post = {labels_url: None}
    getiter = {files_url: []}
    gh = MockGitHubAPI(post=post, delete=delete, getiter=getiter)
    await pull_requests.router.dispatch(event, gh)
    assert f"{labels_url}/{remove_label}" in gh.delete_url
    assert gh.delete_data == []
    assert labels_url in gh.post_url
    assert {"labels": [Label.AWAITING_REVIEW]} in gh.post_data


@pytest.mark.asyncio
async def test_pr_closed():
    remove_label = urllib.parse.quote(Label.AWAITING_REVIEW)
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "issue_url": issue_url,
            "labels": [{"name": Label.AWAITING_REVIEW}],
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    delete = {f"{labels_url}/{remove_label}": None}
    gh = MockGitHubAPI(delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert f"{labels_url}/{remove_label}" in gh.delete_url
    assert gh.delete_data == []
    assert gh.post_url == []
    assert gh.post_data == []
