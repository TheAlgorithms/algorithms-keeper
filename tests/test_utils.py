import urllib.parse
from pathlib import PurePath

import pytest

from algorithms_keeper import utils
from algorithms_keeper.constants import Label

from .utils import (
    MockGitHubAPI,
    check_run_url,
    comment,
    comment_url,
    comments_url,
    contents_url1,
    contents_url2,
    files_url,
    issue_url,
    labels_url,
    number,
    pr_url,
    pr_user_search_url,
    reactions_url,
    repository,
    review_url,
    reviewers_url,
    search_url,
    sha,
    user,
)


@pytest.mark.asyncio
async def test_get_issue_for_commit():
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [{"number": number, "state": "open"}],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_pr_for_commit(gh, sha=sha, repository=repository)
    assert search_url in gh.getitem_url
    assert result["number"] == number
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_get_issue_for_commit_not_found():
    getitem = {
        search_url: {
            "total_count": 0,
            "items": [],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_pr_for_commit(gh, sha=sha, repository=repository)
    assert search_url in gh.getitem_url
    assert result is None


@pytest.mark.asyncio
async def test_get_check_runs_for_commit():
    getitem = {
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "failure"},
            ],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_check_runs_for_commit(gh, sha=sha, repository=repository)
    assert check_run_url in gh.getitem_url
    assert result["total_count"] == 2
    assert [check_run["conclusion"] for check_run in result["check_runs"]] == [
        "success",
        "failure",
    ]
    assert {check_run["status"] for check_run in result["check_runs"]} == {"completed"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_or_issue",
    [{"issue_url": issue_url}, {"labels_url": labels_url}],
)
async def test_add_label_to_pr_or_issue(pr_or_issue):
    gh = MockGitHubAPI()
    await utils.add_label_to_pr_or_issue(
        gh, label=Label.FAILED_TEST, pr_or_issue=pr_or_issue
    )
    assert labels_url in gh.post_url
    assert {"labels": [Label.FAILED_TEST]} in gh.post_data


@pytest.mark.asyncio
async def test_add_multiple_labels():
    pr_or_issue = {"number": number, "issue_url": issue_url}
    gh = MockGitHubAPI()
    await utils.add_label_to_pr_or_issue(
        gh, label=[Label.TYPE_HINT, Label.REVIEW], pr_or_issue=pr_or_issue
    )
    assert labels_url in gh.post_url
    assert {"labels": [Label.TYPE_HINT, Label.REVIEW]} in gh.post_data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_or_issue",
    [{"issue_url": issue_url}, {"labels_url": labels_url}],
)
async def test_remove_label_from_pr_or_issue(pr_or_issue):
    parse_label = urllib.parse.quote(Label.FAILED_TEST)
    gh = MockGitHubAPI()
    await utils.remove_label_from_pr_or_issue(
        gh, label=Label.FAILED_TEST, pr_or_issue=pr_or_issue
    )
    assert f"{labels_url}/{parse_label}" in gh.delete_url


@pytest.mark.asyncio
async def test_remove_multiple_labels():
    parse_label1 = urllib.parse.quote(Label.TYPE_HINT)
    parse_label2 = urllib.parse.quote(Label.REVIEW)
    pr_or_issue = {"issue_url": issue_url}
    gh = MockGitHubAPI()
    await utils.remove_label_from_pr_or_issue(
        gh, label=[Label.TYPE_HINT, Label.REVIEW], pr_or_issue=pr_or_issue
    )
    assert f"{labels_url}/{parse_label1}" in gh.delete_url
    assert f"{labels_url}/{parse_label2}" in gh.delete_url


@pytest.mark.asyncio
async def test_get_user_open_pr_numbers():
    getiter = {
        pr_user_search_url: {
            "total_count": 3,
            "items": [{"number": 1}, {"number": 2}, {"number": 3}],
        }
    }
    gh = MockGitHubAPI(getiter=getiter)
    result = await utils.get_user_open_pr_numbers(
        gh, repository=repository, user_login=user
    )
    assert result == [1, 2, 3]
    assert gh.getiter_url[0] == pr_user_search_url


@pytest.mark.asyncio
async def test_add_comment_to_pr_or_issue():
    # PR and issue both have `comments_url` key.
    pr_or_issue = {"number": number, "comments_url": comments_url}
    gh = MockGitHubAPI()
    await utils.add_comment_to_pr_or_issue(gh, comment=comment, pr_or_issue=pr_or_issue)
    assert comments_url in gh.post_url
    assert {"body": comment} in gh.post_data


@pytest.mark.asyncio
async def test_close_pr_no_reviewers():
    pull_request = {
        "url": pr_url,
        "comments_url": comments_url,
        "requested_reviewers": [],
    }
    gh = MockGitHubAPI()
    await utils.close_pr_or_issue(gh, comment=comment, pr_or_issue=pull_request)
    assert comments_url in gh.post_url
    assert {"body": comment} in gh.post_data
    assert pr_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert gh.delete_url == []  # no reviewers to delete
    assert gh.delete_data == []


@pytest.mark.asyncio
async def test_close_pr_with_reviewers():
    pull_request = {
        "url": pr_url,
        "comments_url": comments_url,
        "requested_reviewers": [{"login": "test1"}, {"login": "test2"}],
    }
    gh = MockGitHubAPI()
    await utils.close_pr_or_issue(gh, comment=comment, pr_or_issue=pull_request)
    assert comments_url in gh.post_url
    assert {"body": comment} in gh.post_data
    assert pr_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert reviewers_url in gh.delete_url
    assert {"reviewers": ["test1", "test2"]} in gh.delete_data


@pytest.mark.asyncio
async def test_close_issue():
    # Issues don't have `requested_reviewers` field.
    issue = {"url": issue_url, "comments_url": comments_url}
    gh = MockGitHubAPI()
    await utils.close_pr_or_issue(gh, comment=comment, pr_or_issue=issue)
    assert comments_url in gh.post_url
    assert {"body": comment} in gh.post_data
    assert issue_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert gh.delete_url == []


@pytest.mark.asyncio
async def test_close_pr_or_issue_with_label():
    # PRs don't have `labels_url` attribute.
    pull_request = {
        "url": pr_url,
        "comments_url": comments_url,
        "issue_url": issue_url,
        "requested_reviewers": [],
    }
    gh = MockGitHubAPI()
    await utils.close_pr_or_issue(
        gh, comment=comment, pr_or_issue=pull_request, label="invalid"
    )
    assert comments_url in gh.post_url
    assert {"body": comment} in gh.post_data
    assert labels_url in gh.post_url
    assert {"labels": ["invalid"]} in gh.post_data
    assert pr_url in gh.patch_url
    assert {"state": "closed"} in gh.patch_data
    assert gh.delete_url == []


@pytest.mark.asyncio
async def test_get_pr_files():
    getiter = {
        files_url: [
            {"filename": "test1.py", "contents_url": contents_url1, "status": "added"},
            {"filename": "test2.py", "contents_url": contents_url2, "status": "added"},
        ]
    }
    pull_request = {"url": pr_url}
    gh = MockGitHubAPI(getiter=getiter)
    result = await utils.get_pr_files(gh, pull_request=pull_request)
    assert len(result) == 2
    assert result[0].name == "test1.py"
    assert result[1].name == "test2.py"
    assert files_url in gh.getiter_url


@pytest.mark.asyncio
async def test_get_added_pr_files():
    getiter = {
        files_url: [
            {"filename": "test1.py", "contents_url": contents_url1, "status": "added"},
            {
                "filename": "test2.py",
                "contents_url": contents_url2,
                "status": "removed",  # We don't want the removed file.
            },
        ]
    }
    pull_request = {"url": pr_url}
    gh = MockGitHubAPI(getiter=getiter)
    result = await utils.get_pr_files(gh, pull_request=pull_request)
    assert len(result) == 1
    assert result[0].name == "test1.py"
    assert files_url in gh.getiter_url


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
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_file_content(
        gh, file=utils.File("test.py", PurePath("test.py"), contents_url1, "added")
    )
    assert result == (
        b'def test1(a, b, c):\n\t"""\n\tA test function\n\t"""\n\treturn False'
        b'\n\ndef test2(d, e, f):\n\t"""\n\tA test function\n\t"""\n\treturn None'
        b'\n\ndef test3(a: int) -> None:\n\t"""\n\t>>> findIslands(1, 1, 1)\n\t"""'
        b"\n\treturn None\n\nif __name__ == '__main__':\n\tpass\n"
    )
    assert contents_url1 in gh.getitem_url


@pytest.mark.asyncio
async def test_create_pr_review():
    pull_request = {"url": pr_url, "head": {"sha": sha}}
    gh = MockGitHubAPI()
    await utils.create_pr_review(
        gh, pull_request=pull_request, comments=[{"body": "test"}]
    )
    assert review_url in gh.post_url
    assert gh.post_data[0]["event"] == "COMMENT"


@pytest.mark.asyncio
async def test_add_reaction():
    comment = {"url": comment_url}
    gh = MockGitHubAPI()
    await utils.add_reaction(gh, reaction="+1", comment=comment)
    assert reactions_url in gh.post_url
    assert {"content": "+1"} in gh.post_data


@pytest.mark.asyncio
async def test_get_pr_for_issue():
    getitem = {pr_url: None}
    issue = {"pull_request": {"url": pr_url}}
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_pr_for_issue(gh, issue=issue)
    assert result is None
    assert pr_url in gh.getitem_url
