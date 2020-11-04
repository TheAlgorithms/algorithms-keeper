import urllib.parse

import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import apps, sansio

from algobot import pull_requests, utils
from algobot.constants import Label
from algobot.pull_requests import (
    CHECKBOX_NOT_TICKED_COMMENT,
    EMPTY_BODY_COMMENT,
    MAX_PR_REACHED_COMMENT,
    NO_EXTENSION_COMMENT,
)

from .test_parser import get_file_code
from .utils import MOCK_INSTALLATION_ID, MockGitHubAPI, mock_return

# Common constants
number = 1
user = "test"
repository = "TheAlgorithms/Python"
sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
comment = "This is a comment"

# Incomplete urls
search_url = f"/search/issues?q=type:pr+state:open+repo:{repository}+sha:{sha}"
pr_search_url = f"/search/issues?q=type:pr+state:open+repo:{repository}"
pr_user_search_url = (
    f"/search/issues?q=type:pr+state:open+repo:{repository}+author:{user}"
)

# Complete urls
html_pr_url = f"https://github.com/{repository}/pulls/{number}"
pr_url = f"https://api.github.com/repos/{repository}/pulls/{number}"
issue_url = f"https://api.github.com/repos/{repository}/issues/{number}"
labels_url = issue_url + "/labels"
comments_url = issue_url + "/comments"
reviewers_url = pr_url + "/requested_reviewers"
files_url = pr_url + "/files"

# PR template ticked
CHECKBOX_TICKED = (
    "### **Describe your change:**\r\n\r\n\r\n\r\n* [ ] Add an algorithm?\r\n* [x]"
    " Fix a bug or typo in an existing algorithm?\r\n* [x] Documentation change?"
    "\r\n\r\n### **Checklist:**\r\n* [x] I have read [CONTRIBUTING.md]"
    "(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md).\r\n* "
    "[x] This pull request is all my own work -- I have not plagiarized.\r\n* [x] "
    "I know that pull requests will not be merged if they fail the automated tests."
    "\r\n* [x] This PR only changes one algorithm file.  To ease review, please open "
    "separate PRs for separate algorithms.\r\n* [x] All new Python files are placed "
    "inside an existing directory.\r\n* [x] All filenames are in all lowercase "
    "characters with no spaces or dashes.\r\n* [x] All functions and variable names "
    "follow Python naming conventions.\r\n* [x] All function parameters and return "
    "values are annotated with Python [type hints]"
    "(https://docs.python.org/3/library/typing.html).\r\n* [x] All functions have "
    "[doctests](https://docs.python.org/3/library/doctest.html) that pass the "
    "automated testing.\r\n* [x] All new algorithms have a URL in its comments that "
    "points to Wikipedia or other similar explanation.\r\n* [ ] If this pull request "
    "resolves one or more open issues then the commit message contains "
    "`Fixes: #{$ISSUE_NO}`.\r\n"
)

# PR template not ticked
CHECKBOX_NOT_TICKED = (
    "### **Describe your change:**\r\n\r\n\r\n\r\n* [ ] Add an algorithm?\r\n* [ ]"
    " Fix a bug or typo in an existing algorithm?\r\n* [ ] Documentation change?"
    "\r\n\r\n### **Checklist:**\r\n* [ ] I have read [CONTRIBUTING.md]"
    "(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md).\r\n* "
    "[ ] This pull request is all my own work -- I have not plagiarized.\r\n* [ ] "
    "I know that pull requests will not be merged if they fail the automated tests."
    "\r\n* [ ] This PR only changes one algorithm file.  To ease review, please open "
    "separate PRs for separate algorithms.\r\n* [ ] All new Python files are placed "
    "inside an existing directory.\r\n* [ ] All filenames are in all lowercase "
    "characters with no spaces or dashes.\r\n* [ ] All functions and variable names "
    "follow Python naming conventions.\r\n* [ ] All function parameters and return "
    "values are annotated with Python [type hints]"
    "(https://docs.python.org/3/library/typing.html).\r\n* [ ] All functions have "
    "[doctests](https://docs.python.org/3/library/doctest.html) that pass the "
    "automated testing.\r\n* [ ] All new algorithms have a URL in its comments that "
    "points to Wikipedia or other similar explanation.\r\n* [ ] If this pull request "
    "resolves one or more open issues then the commit message contains "
    "`Fixes: #{$ISSUE_NO}`.\r\n"
)

# Comment constants
EMPTY_BODY_COMMENT = EMPTY_BODY_COMMENT.format(user_login=user)
CHECKBOX_NOT_TICKED_COMMENT = CHECKBOX_NOT_TICKED_COMMENT.format(user_login=user)
NO_EXTENSION_COMMENT = NO_EXTENSION_COMMENT.format(user_login=user)


@pytest.fixture(scope="module", autouse=True)
def patch_module(monkeypatch=MonkeyPatch()):
    async def mock_get_file_content(gh, installation_id, file):
        if file["filename"] in {
            "require_doctest.py",
            "require_annotations.py",
            "require_descriptive_names.py",
            "require_return_annotation.py",
        }:
            return get_file_code(file["filename"])
        else:
            return ""

    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    monkeypatch.setattr(utils, "get_file_content", mock_get_file_content)
    yield monkeypatch
    monkeypatch.undo()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body, comment",
    (
        ("", EMPTY_BODY_COMMENT),
        (CHECKBOX_NOT_TICKED, CHECKBOX_NOT_TICKED_COMMENT),
    ),
)
async def test_pr_opened_no_body_and_no_ticked(body, comment):
    data = {
        "action": "opened",
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": body,
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {files_url: []}
    post = {labels_url: {}, comments_url: {}}
    patch = {pr_url: {}}
    delete = {reviewers_url: {}}
    gh = MockGitHubAPI(getiter=getiter, post=post, patch=patch, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert gh.getiter_url[0] == files_url
    assert len(gh.post_url) == 2
    assert gh.post_url == [comments_url, labels_url]
    assert gh.post_data[0] == {"body": comment}
    assert gh.post_data[1] == {"labels": ["invalid"]}
    assert gh.patch_url[0] == pr_url
    assert gh.patch_data[0] == {"state": "closed"}
    assert gh.delete_url[0] == reviewers_url
    assert gh.delete_data[0] == {"reviewers": ["test1", "test2"]}


@pytest.mark.asyncio
async def test_pr_opened_by_member():
    data = {
        "action": "opened",
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": "",  # body can be empty for member
            "labels": [],
            "user": {"login": user},
            "author_association": "MEMBER",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {files_url: []}  # for check_pr_files function
    gh = MockGitHubAPI(getiter=getiter)
    await pull_requests.router.dispatch(event, gh)
    assert gh.getiter_url[0] == files_url
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.patch_url == []
    assert gh.patch_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_max_pr_reached():
    data = {
        "action": "opened",
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {
        pr_user_search_url: {
            "total_count": 2,
            "items": [
                {"number": 1, "state": "opened"},
                {"number": 2, "state": "opened"},
            ],
        },
        files_url: [],  # for check_pr_files function
    }
    post = {comments_url: {}}
    patch = {pr_url: {}}
    delete = {reviewers_url: {}}
    gh = MockGitHubAPI(getiter=getiter, post=post, patch=patch, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    assert gh.getiter_url[0] == pr_user_search_url
    assert gh.post_url[0] == comments_url
    assert gh.post_data[0] == {
        "body": MAX_PR_REACHED_COMMENT.format(user_login=user, pr_number="#1, #2")
    }
    assert gh.patch_url[0] == pr_url
    assert gh.delete_url[0] == reviewers_url
    assert gh.delete_data[0] == {"reviewers": ["test1", "test2"]}


@pytest.mark.asyncio
async def test_max_pr_disabled(monkeypatch):
    monkeypatch.setattr(pull_requests, "MAX_PR_PER_USER", 0)
    data = {
        "action": "opened",
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    getiter = {files_url: []}
    gh = MockGitHubAPI(getiter=getiter)
    await pull_requests.router.dispatch(event, gh)
    assert gh.getiter_url[0] == files_url
    # No changes as max pr checks are disabled
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.patch_url == []
    assert gh.delete_url == []
    assert gh.delete_data == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, getiter",
    (
        (
            "opened",
            {
                pr_user_search_url: {
                    "total_count": 1,
                    "items": [
                        {"number": 1, "state": "opened"},
                    ],
                },
                files_url: [
                    {"filename": "newton.py", "contents_url": ""},
                    {"filename": "fibonacci", "contents_url": ""},
                ],
            },
        ),
        (
            "synchronize",
            {
                files_url: [
                    {"filename": "newton.py", "contents_url": ""},
                    {"filename": "fibonacci", "contents_url": ""},
                ],
            },
        ),
    ),
)
async def test_for_extensionless_files_on_opened(action, getiter):
    data = {
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {comments_url: {}, labels_url: {}}
    patch = {pr_url: {}}
    delete = {reviewers_url: {}}
    gh = MockGitHubAPI(getiter=getiter, post=post, patch=patch, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    if event.data["action"] == "opened":
        assert len(gh.getiter_url) == 2
        assert gh.getiter_url == [pr_user_search_url, files_url]
    elif event.data["action"] == "synchronize":
        assert len(gh.getiter_url) == 1
        assert gh.getiter_url[0] == files_url
    assert len(gh.post_url) == 2
    assert gh.post_url == [comments_url, labels_url]
    assert gh.post_data[0] == {"body": NO_EXTENSION_COMMENT}
    assert gh.post_data[1] == {"labels": ["invalid"]}
    assert gh.patch_url[0] == pr_url
    assert gh.patch_data[0] == {"state": "closed"}
    assert gh.delete_url[0] == reviewers_url
    assert gh.delete_data[0] == {"reviewers": ["test1", "test2"]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, getiter",
    (
        (
            "opened",
            {
                pr_user_search_url: {
                    "total_count": 1,
                    "items": [
                        {"number": 1, "state": "opened"},
                    ],
                },
                files_url: [
                    {"filename": ".travis.yml", "contents_url": ""},
                    {"filename": "README.md", "contents_url": ""},
                    {"filename": "pytest.ini", "contents_url": ""},
                ],
            },
        ),
        (
            "synchronize",
            {
                files_url: [
                    {"filename": ".travis.yml", "contents_url": ""},
                    {"filename": "README.md", "contents_url": ""},
                    {"filename": "__init__.py", "contents_url": ""},
                ],  # We will add one `__` Python file in the mix
            },
        ),
    ),
)
async def test_pr_with_no_python_files(action, getiter):
    data = {
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            "labels": [],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = MockGitHubAPI(getiter=getiter)
    await pull_requests.router.dispatch(event, gh)
    if data["action"] == "opened":
        assert len(gh.getiter_url) == 2
        assert gh.getiter_url == [pr_user_search_url, files_url]
    elif data["action"] == "synchronize":
        assert len(gh.getiter_url) == 1
        assert gh.getiter_url == [files_url]
    # Nothing happens as there are no Python files
    assert gh.post_url == []
    assert gh.post_data == []
    assert gh.patch_url == []
    assert gh.patch_data == []
    assert gh.delete_url == []
    assert gh.delete_data == []


# From this point on, as we have tested the `PullRequestFilesParser` in a separate
# file we will assume that the logic is correct for the class. With that in mind,
# we will only test the logic of the `check_pr_files` function and not whether the
# parser is working accordingly or not.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, getiter",
    (
        (
            "opened",
            {
                pr_user_search_url: {
                    "total_count": 1,
                    "items": [
                        {"number": 1, "state": "opened"},
                    ],
                },
                files_url: [
                    {"filename": "require_doctest.py", "contents_url": ""},
                    {"filename": "test_algo.py", "contents_url": ""},
                    {"filename": "require_annotations.py", "contents_url": ""},
                ],
            },
        ),
        (
            "synchronize",
            {
                files_url: [
                    {"filename": "require_doctest.py", "contents_url": ""},
                    {"filename": "test_algo.py", "contents_url": ""},
                    {"filename": "require_annotations.py", "contents_url": ""},
                ],
            },
        ),
    ),
)
async def test_pr_with_test_file(action, getiter):
    remove_label = urllib.parse.quote(Label.REQUIRE_TEST)
    data = {
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "url": pr_url,
            "body": CHECKBOX_TICKED,
            # This is like a marker to test the function, the label should be removed
            "labels": [{"name": Label.REQUIRE_TEST}],
            "user": {"login": user},
            "author_association": "NONE",
            "comments_url": comments_url,
            "issue_url": issue_url,
            "html_url": html_pr_url,
            "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
        },
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    post = {labels_url: {}, comments_url: {}}
    delete = {labels_url + f"/{remove_label}": {}}
    gh = MockGitHubAPI(getiter=getiter, post=post, delete=delete)
    await pull_requests.router.dispatch(event, gh)
    if data["action"] == "opened":
        assert len(gh.getiter_url) == 2
        assert gh.getiter_url == [pr_user_search_url, files_url]
        assert len(gh.post_url) == 2
        assert gh.post_url == [labels_url, comments_url]
    elif data["action"] == "synchronize":
        assert len(gh.getiter_url) == 1
        assert gh.getiter_url[0] == files_url
        assert len(gh.post_url) == 1
        # No comment is posted in `synchronize`
        assert gh.post_url == [labels_url]
    assert gh.post_data[0] == {"labels": [Label.ANNOTATIONS]}
    assert gh.delete_url[0] == labels_url + f"/{remove_label}"
    assert gh.delete_data == [{}]
