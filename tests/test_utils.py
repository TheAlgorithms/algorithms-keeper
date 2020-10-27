import urllib.parse

import pytest
from gidgethub import apps

from algobot import utils
from algobot.check_runs import FAILURE_LABEL

from .utils import MockGitHubAPI

MOCK_TOKEN = 19
MOCK_INSTALLATION_ID = 1234


async def mock_return(*args, **kwargs):
    return {"token": MOCK_TOKEN}


@pytest.mark.asyncio
async def test_get_access_token(monkeypatch):
    gh = MockGitHubAPI()
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
async def test_get_pr_for_commit():
    sha = "7854eeaf24aa3d4eada256b6223d8d4ed05f63a1"
    repository = "TheAlgorithms/Python"
    gh = MockGitHubAPI(
        getitem={
            f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
                "total_count": 1,
                "incomplete_results": False,
                "items": [
                    {
                        "number": 3704,
                        "title": "Move validate_solutions and add durations flag to pytest.ini",
                        "state": "closed",
                    }
                ],
            }
        }
    )
    result = await utils.get_pr_for_commit(sha, gh, MOCK_INSTALLATION_ID, repository)
    assert gh.getitem_url == f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}"
    assert result["number"] == 3704
    assert (
        result["title"]
        == "Move validate_solutions and add durations flag to pytest.ini"
    )
    assert result["state"] == "closed"


@pytest.mark.asyncio
async def test_get_pr_for_commit_not_found():
    sha = "1854eeaf24aa3d4eada256b6223d8d4ed05f63a1"
    repository = "TheAlgorithms/Python"
    gh = MockGitHubAPI(
        getitem={
            f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
                "total_count": 0,
                "incomplete_results": False,
                "items": [],
            }
        }
    )
    result = await utils.get_pr_for_commit(sha, gh, MOCK_INSTALLATION_ID, repository)
    assert gh.getitem_url == f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}"
    assert result is None


@pytest.mark.asyncio
async def test_get_check_runs_for_commit():
    sha = "920a347a8fdbe9a58ea35b81c54b4c8b877114c5"
    repository = "TheAlgorithms/Python"
    gh = MockGitHubAPI(
        getitem={
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
    )
    result = await utils.get_check_runs_for_commit(
        sha, gh, MOCK_INSTALLATION_ID, repository
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
async def test_add_label_to_pr():
    label = FAILURE_LABEL
    pr_number = 2526
    repository = "TheAlgorithms/Python"
    gh = MockGitHubAPI(
        post=[
            {"name": "Require: Tests", "color": "fbca04"},
            {"name": "Require: Type hints", "color": "fbca04"},
            {"name": "Status: Tests are failing", "color": "d93f0b"},
            {"name": "Status: awaiting changes", "color": "7ae8b3"},
        ]
    )
    result = await utils.add_label_to_pr(
        label, pr_number, gh, MOCK_INSTALLATION_ID, repository
    )
    assert gh.post_url == f"/repos/{repository}/issues/{pr_number}/labels"
    assert gh.post_data == {"labels": [label]}
    assert result is None


@pytest.mark.asyncio
async def test_remove_label_from_pr():
    label = FAILURE_LABEL
    parse_label = urllib.parse.quote(label)
    pr_number = 2526
    repository = "TheAlgorithms/Python"
    gh = MockGitHubAPI(
        delete=[
            {"name": "Require: Tests", "color": "fbca04"},
            {"name": "Require: Type hints", "color": "fbca04"},
            {"name": "Status: awaiting changes", "color": "7ae8b3"},
        ]
    )
    result = await utils.remove_label_from_pr(
        label, pr_number, gh, MOCK_INSTALLATION_ID, repository
    )
    assert (
        gh.delete_url == f"/repos/{repository}/issues/{pr_number}/labels/{parse_label}"
    )
    assert result is None
