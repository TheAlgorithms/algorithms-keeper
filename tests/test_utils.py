import urllib.parse

import pytest
from gidgethub import apps

from algorithms_keeper import utils
from algorithms_keeper.constants import Label

from .utils import MOCK_INSTALLATION_ID, MOCK_TOKEN, MockGitHubAPI, mock_return

# Common test constants
user = "test"
number = 1
sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
repository = "TheAlgorithms/Python"
comment = "This is a test comment"

# Incomplete urls
search_url = (
    f"/search/issues?q=type:pr+state:open+draft:false+repo:{repository}+sha:{sha}"
)
pr_search_url = f"/search/issues?q=type:pr+state:open+repo:{repository}"
pr_user_search_url = (
    f"/search/issues?q=type:pr+state:open+repo:{repository}+author:{user}"
)
check_run_url = f"/repos/{repository}/commits/{sha}/check-runs"

# Complete urls
pr_url = f"https://api.github.com/repos/{repository}/pulls/{number}"
issue_url = f"https://api.github.com/repos/{repository}/issues/{number}"
labels_url = issue_url + "/labels"
comments_url = issue_url + "/comments"
reviewers_url = pr_url + "/requested_reviewers"
files_url = pr_url + "/files"
contents_url1 = f"https://api.github.com/repos/{repository}/contents/test1.py?ref={sha}"
contents_url2 = f"https://api.github.com/repos/{repository}/contents/test2.py?ref={sha}"


@pytest.mark.asyncio
async def test_get_access_token(monkeypatch):
    gh = MockGitHubAPI()
    utils.cache.clear()  # Make sure the cache is cleared
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    token = await utils.get_access_token(gh, MOCK_INSTALLATION_ID)
    assert token == MOCK_TOKEN
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_cached_access_token(monkeypatch):
    gh = MockGitHubAPI()
    # This is to make sure it actually returns the cached token
    monkeypatch.delattr(apps, "get_installation_access_token")
    token = await utils.get_access_token(gh, MOCK_INSTALLATION_ID)
    assert token == MOCK_TOKEN
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_issue_for_commit():
    getitem = {
        search_url: {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": number,
                    "state": "open",
                }
            ],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_pr_for_commit(
        gh, MOCK_INSTALLATION_ID, sha=sha, repository=repository
    )
    assert gh.getitem_url[0] == search_url
    assert result["number"] == number
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_get_issue_for_commit_not_found():
    getitem = {
        search_url: {
            "total_count": 0,
            "incomplete_results": False,
            "items": [],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_pr_for_commit(
        gh, MOCK_INSTALLATION_ID, sha=sha, repository=repository
    )
    assert gh.getitem_url[0] == search_url
    assert result is None


@pytest.mark.asyncio
async def test_get_check_runs_for_commit():
    getitem = {
        check_run_url: {
            "total_count": 4,
            "check_runs": [
                {
                    "status": "completed",
                    "conclusion": "success",
                    "name": "build",
                },
                {
                    "status": "completed",
                    "conclusion": "failure",
                    "name": "pre-commit",
                },
                {
                    "status": "completed",
                    "conclusion": "failure",
                    "name": "pre-commit",
                },
                {
                    "status": "completed",
                    "conclusion": "action_required",
                    "name": "Travis CI - Pull Request",
                },
            ],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_check_runs_for_commit(
        gh, MOCK_INSTALLATION_ID, sha=sha, repository=repository
    )
    assert gh.getitem_url[0] == check_run_url
    assert result["total_count"] == 4
    assert [check_run["conclusion"] for check_run in result["check_runs"]] == [
        "success",
        "failure",
        "failure",
        "action_required",
    ]
    assert {check_run["status"] for check_run in result["check_runs"]} == {"completed"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_or_issue",
    [
        {"number": number, "issue_url": issue_url},
        {"number": number, "labels_url": labels_url},
    ],
)
async def test_add_label_to_pr_or_issue(pr_or_issue):
    post = {
        labels_url: [
            {"name": Label.ANNOTATIONS},
            {"name": Label.FAILED_TEST},
        ]
    }
    gh = MockGitHubAPI(post=post)
    result = await utils.add_label_to_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, label=Label.FAILED_TEST, pr_or_issue=pr_or_issue
    )
    assert gh.post_url[0] == labels_url
    assert gh.post_data[0] == {"labels": [Label.FAILED_TEST]}
    assert result is None


@pytest.mark.asyncio
async def test_add_multiple_labels():
    pr_or_issue = {"number": number, "issue_url": issue_url}
    post = {
        labels_url: [
            {"name": Label.ANNOTATIONS},
            {"name": Label.FAILED_TEST},
        ]
    }
    gh = MockGitHubAPI(post=post)
    result = await utils.add_label_to_pr_or_issue(
        gh,
        MOCK_INSTALLATION_ID,
        label=[Label.ANNOTATIONS, Label.AWAITING_REVIEW],
        pr_or_issue=pr_or_issue,
    )
    assert gh.post_url[0] == labels_url
    assert gh.post_data[0] == {"labels": [Label.ANNOTATIONS, Label.AWAITING_REVIEW]}
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_or_issue",
    [
        {"number": number, "issue_url": issue_url},
        {"number": number, "labels_url": labels_url},
    ],
)
async def test_remove_label_from_pr(pr_or_issue):
    parse_label = urllib.parse.quote(Label.FAILED_TEST)
    delete = {labels_url + f"/{parse_label}": [{"name": Label.ANNOTATIONS}]}
    gh = MockGitHubAPI(delete=delete)
    result = await utils.remove_label_from_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, label=Label.FAILED_TEST, pr_or_issue=pr_or_issue
    )
    assert gh.delete_url[0] == labels_url + f"/{parse_label}"
    assert result is None


@pytest.mark.asyncio
async def test_remove_multiple_labels():
    parse_label1 = urllib.parse.quote(Label.ANNOTATIONS)
    parse_label2 = urllib.parse.quote(Label.AWAITING_REVIEW)
    pr_or_issue = {"number": number, "issue_url": issue_url}
    delete = {
        labels_url + f"/{parse_label1}": [],
        labels_url + f"/{parse_label2}": [],
    }
    gh = MockGitHubAPI(delete=delete)
    result = await utils.remove_label_from_pr_or_issue(
        gh,
        MOCK_INSTALLATION_ID,
        label=[Label.ANNOTATIONS, Label.AWAITING_REVIEW],
        pr_or_issue=pr_or_issue,
    )
    assert gh.delete_url[0] == labels_url + f"/{parse_label1}"
    assert gh.delete_url[1] == labels_url + f"/{parse_label2}"
    assert result is None


@pytest.mark.asyncio
async def test_get_total_open_prs_for_repo():
    getitem = {pr_search_url: {"total_count": 10, "items": []}}
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_total_open_prs(
        gh, MOCK_INSTALLATION_ID, repository=repository
    )
    assert result == 10
    assert gh.getitem_url[0] == pr_search_url


@pytest.mark.asyncio
async def test_get_total_open_prs_for_user():
    getitem = {pr_user_search_url: {"total_count": 10, "items": []}}
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_total_open_prs(
        gh, MOCK_INSTALLATION_ID, repository=repository, user_login=user
    )
    assert result == 10
    assert gh.getitem_url[0] == pr_user_search_url


@pytest.mark.asyncio
async def test_get_total_open_pr_numbers_for_repo():
    getiter = {
        pr_search_url: {
            "total_count": 3,
            "items": [{"number": 1}, {"number": 2}, {"number": 3}],
        }
    }
    gh = MockGitHubAPI(getiter=getiter)
    result = await utils.get_total_open_prs(
        gh, MOCK_INSTALLATION_ID, repository=repository, count=False
    )
    assert result == [1, 2, 3]
    assert gh.getiter_url[0] == pr_search_url


@pytest.mark.asyncio
async def test_get_total_open_pr_numbers_for_user():
    getiter = {
        pr_user_search_url: {
            "total_count": 3,
            "items": [{"number": 1}, {"number": 2}, {"number": 3}],
        }
    }
    gh = MockGitHubAPI(getiter=getiter)
    result = await utils.get_total_open_prs(
        gh, MOCK_INSTALLATION_ID, repository=repository, user_login=user, count=False
    )
    assert result == [1, 2, 3]
    assert gh.getiter_url[0] == pr_user_search_url


@pytest.mark.asyncio
async def test_add_comment_to_pr_or_issue():
    # PR and issue both have `comments_url` key
    pr_or_issue = {"number": number, "comments_url": comments_url}
    post = {comments_url: {}}
    gh = MockGitHubAPI(post=post)
    result = await utils.add_comment_to_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, comment=comment, pr_or_issue=pr_or_issue
    )
    assert gh.post_url[0] == comments_url
    assert gh.post_data[0] == {"body": comment}
    assert result is None


@pytest.mark.asyncio
async def test_close_pr_no_reviewers():
    pull_request = {
        "url": pr_url,
        "comments_url": comments_url,
        "requested_reviewers": [],
    }
    post = {comments_url: {}}
    patch = {pr_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    result = await utils.close_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, comment=comment, pr_or_issue=pull_request
    )
    assert gh.post_url[0] == comments_url
    assert gh.post_data[0] == {"body": comment}
    assert gh.patch_url[0] == pr_url
    assert gh.patch_data[0] == {"state": "closed"}
    assert gh.delete_url == []  # no reviewers to delete
    assert result is None


@pytest.mark.asyncio
async def test_close_pr_with_reviewers():
    pull_request = {
        "url": pr_url,
        "comments_url": comments_url,
        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
    }
    post = {comments_url: {}}
    patch = {pr_url: {}}
    delete = {reviewers_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch, delete=delete)
    result = await utils.close_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, comment=comment, pr_or_issue=pull_request
    )
    assert gh.post_url[0] == comments_url
    assert gh.post_data[0] == {"body": comment}
    assert gh.patch_url[0] == pr_url
    assert gh.patch_data[0] == {"state": "closed"}
    assert gh.delete_url[0] == reviewers_url
    assert result is None


@pytest.mark.asyncio
async def test_close_issue():
    # issues don't have `requested_reviewers` field
    issue = {"url": issue_url, "comments_url": comments_url}
    post = {comments_url: {}}
    patch = {issue_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    result = await utils.close_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, comment=comment, pr_or_issue=issue
    )
    assert gh.post_url[0] == comments_url
    assert gh.post_data[0] == {"body": comment}
    assert gh.patch_url[0] == issue_url
    assert gh.patch_data[0] == {"state": "closed"}
    assert gh.delete_url == []
    assert result is None


@pytest.mark.asyncio
async def test_close_pr_or_issue_with_label():
    # PRs don't have `labels_url` attribute
    pull_request = {
        "url": pr_url,
        "comments_url": comments_url,
        "issue_url": issue_url,
        "requested_reviewers": [],
    }
    post = {comments_url: {}, labels_url: {}}
    patch = {pr_url: {}}
    gh = MockGitHubAPI(post=post, patch=patch)
    result = await utils.close_pr_or_issue(
        gh,
        MOCK_INSTALLATION_ID,
        comment=comment,
        pr_or_issue=pull_request,
        label="invalid",
    )
    assert gh.post_url[0] == comments_url
    assert gh.post_data[0] == {"body": comment}
    assert gh.post_url[1] == labels_url
    assert gh.post_data[1] == {"labels": ["invalid"]}
    assert gh.patch_url[0] == pr_url
    assert gh.patch_data[0] == {"state": "closed"}
    assert gh.delete_url == []
    assert result is None


@pytest.mark.asyncio
async def test_get_pr_files():
    files = [
        {"filename": "test1.py", "contents_url": contents_url1, "status": "added"},
        {"filename": "test2.py", "contents_url": contents_url2, "status": "added"},
    ]
    getiter = {files_url: files}
    pull_request = {"url": pr_url}
    gh = MockGitHubAPI(getiter=getiter)
    result = await utils.get_pr_files(
        gh, MOCK_INSTALLATION_ID, pull_request=pull_request
    )
    assert result == [
        {"filename": "test1.py", "contents_url": contents_url1},
        {"filename": "test2.py", "contents_url": contents_url2},
    ]
    assert gh.getiter_url[0] == files_url


@pytest.mark.asyncio
async def test_get_file_content():
    getitem = {
        contents_url1: {
            "content": (
                "ZGVmIHRlc3QxKGEsIGIsIGMpOgoJIiIiCglBIHRlc3QgZnVuY3Rpb24KCSI"
                "i\nIgoJcmV0dXJuIEZhbHNlCgpkZWYgdGVzdDIoZCwgZSwgZik6CgkiIiIKC"
                "UEg\ndGVzdCBmdW5jdGlvbgoJIiIiCglyZXR1cm4gTm9uZQoKZGVmIHRlc3Q"
                "zKGE6\nIGludCkgLT4gTm9uZToKCSIiIgoJPj4+IGZpbmRJc2xhbmRzKDEsID"
                "EsIDEp\nCgkiIiIKCXJldHVybiBOb25lCgppZiBfX25hbWVfXyA9PSAnX19tY"
                "WluX18n\nOgoJcGFzcwo=\n"
            )
        }
    }
    output = (
        b'def test1(a, b, c):\n\t"""\n\tA test function\n\t"""\n\treturn False'
        b'\n\ndef test2(d, e, f):\n\t"""\n\tA test function\n\t"""\n\treturn None'
        b'\n\ndef test3(a: int) -> None:\n\t"""\n\t>>> findIslands(1, 1, 1)\n\t"""'
        b"\n\treturn None\n\nif __name__ == '__main__':\n\tpass\n"
    )
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_file_content(
        gh,
        MOCK_INSTALLATION_ID,
        file={"filename": "test.py", "contents_url": contents_url1},
    )
    assert result == output
    assert gh.getitem_url[0] == contents_url1
