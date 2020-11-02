import urllib.parse

import pytest
from gidgethub import apps

from algobot import utils
from algobot.constants import Label

from .utils import MOCK_INSTALLATION_ID, MOCK_TOKEN, MockGitHubAPI, mock_return


@pytest.mark.asyncio
async def test_get_access_token(monkeypatch):
    gh = MockGitHubAPI()
    utils.cache.clear()  # Make sure the cache is cleared
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    token = await utils.get_access_token(gh, MOCK_INSTALLATION_ID)
    assert token == MOCK_TOKEN


@pytest.mark.asyncio
async def test_get_cached_access_token(monkeypatch):
    gh = MockGitHubAPI()
    # This is to make sure it actually returns the cached token
    monkeypatch.delattr(apps, "get_installation_access_token")
    token = await utils.get_access_token(gh, MOCK_INSTALLATION_ID)
    assert token == MOCK_TOKEN


@pytest.mark.asyncio
async def test_get_issue_for_commit():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
    getitem = {
        f"/search/issues?q=type:pr+state:open+repo:{repository}+sha:{sha}": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 3378,
                    "title": "Create GitHub action only for Project Euler",
                    "state": "open",
                }
            ],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_issue_for_commit(
        gh, MOCK_INSTALLATION_ID, sha=sha, repository=repository
    )
    assert (
        gh.getitem_url
        == f"/search/issues?q=type:pr+state:open+repo:{repository}+sha:{sha}"
    )
    assert result["number"] == 3378
    assert result["title"] == "Create GitHub action only for Project Euler"
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_get_issue_for_commit_not_found():
    sha = "1854eeaf24aa3d4eada256b6223d8d4ed05f63a1"
    repository = "TheAlgorithms/Python"
    getitem = {
        f"/search/issues?q=type:pr+state:open+repo:{repository}+sha:{sha}": {
            "total_count": 0,
            "incomplete_results": False,
            "items": [],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await utils.get_issue_for_commit(
        gh, MOCK_INSTALLATION_ID, sha=sha, repository=repository
    )
    assert (
        gh.getitem_url
        == f"/search/issues?q=type:pr+state:open+repo:{repository}+sha:{sha}"
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_check_runs_for_commit():
    sha = "920a347a8fdbe9a58ea35b81c54b4c8b877114c5"
    repository = "TheAlgorithms/Python"
    getitem = {
        f"/repos/{repository}/commits/{sha}/check-runs": {
            "total_count": 4,
            "check_runs": [
                {"status": "completed", "conclusion": "success", "name": "build"},
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
    assert gh.getitem_url == f"/repos/{repository}/commits/{sha}/check-runs"
    assert result["total_count"] == 4
    assert [check_run["conclusion"] for check_run in result["check_runs"]] == [
        "success",
        "failure",
        "failure",
        "action_required",
    ]
    assert {check_run["status"] for check_run in result["check_runs"]} == {"completed"}


@pytest.mark.asyncio
async def test_add_label_to_pr_or_issue():
    repository = "TheAlgorithms/Python"
    pull_request = {
        "number": 2526,
        "issue_url": f"https://api.github.com/repos/{repository}/issues/2526",
    }
    post = [
        {"name": "Require: Tests", "color": "fbca04"},
        {"name": "Require: Type hints", "color": "fbca04"},
        {"name": Label.FAILED_TEST, "color": "d93f0b"},
        {"name": "Status: awaiting changes", "color": "7ae8b3"},
    ]
    gh = MockGitHubAPI(post=post)
    result = await utils.add_label_to_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, label=Label.FAILED_TEST, pr_or_issue=pull_request
    )
    assert (
        gh.post_url == f"https://api.github.com/repos/{repository}/issues/2526/labels"
    )
    assert gh.post_data == {"labels": [Label.FAILED_TEST]}
    assert result is None


@pytest.mark.asyncio
async def test_remove_label_from_pr_or_issue():
    parse_label = urllib.parse.quote(Label.FAILED_TEST)
    repository = "TheAlgorithms/Python"
    pull_request = {
        "number": 2526,
        "issue_url": f"https://api.github.com/repos/{repository}/issues/2526",
    }
    delete = [
        {"name": "Require: Tests", "color": "fbca04"},
        {"name": "Require: Type hints", "color": "fbca04"},
        {"name": "Status: awaiting changes", "color": "7ae8b3"},
    ]
    gh = MockGitHubAPI(delete=delete)
    result = await utils.remove_label_from_pr_or_issue(
        gh, MOCK_INSTALLATION_ID, label=Label.FAILED_TEST, pr_or_issue=pull_request
    )
    assert (
        gh.delete_url
        == f"https://api.github.com/repos/{repository}/issues/2526/labels/{parse_label}"
    )
    assert result is None
