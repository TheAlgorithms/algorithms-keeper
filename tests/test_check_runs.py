import urllib.parse

import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import apps, sansio

from algobot import check_runs
from algobot.constants import Label

from .utils import MOCK_INSTALLATION_ID, MockGitHubAPI, mock_return

# Common constants
number = 1
repository = "TheAlgorithms/Python"
sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"

# Incomplete urls
html_pr_url = f"https://github.com/{repository}/pulls/{number}"
search_url = f"/search/issues?q=type:pr+state:open+repo:{repository}+sha:{sha}"
check_run_url = f"/repos/{repository}/commits/{sha}/check-runs"
labels_url = f"https://api.github.com/repos/{repository}/issues/{number}/labels"


@pytest.fixture(scope="module", autouse=True)
def patch_module(monkeypatch=MonkeyPatch()):
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)
    yield monkeypatch
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_check_run_created():
    data = {
        "action": "created",
        "check_run": {
            "status": "queued",
            "conclusion": None,
        },
        "name": "pre-commit",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="1")
    gh = MockGitHubAPI()
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert gh.getitem_url == []
    assert gh.post_url == []  # does not add any label
    assert gh.post_data == []
    assert gh.delete_url == []  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_not_from_pr_commit():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
        },
        "name": "pre-commit",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="2")
    getitem = {
        search_url: {
            "total_count": 0,
            "items": [],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 1
    assert gh.getitem_url[0] == search_url
    assert gh.post_url == []  # does not add any label
    assert gh.post_data == []
    assert gh.delete_url == []  # does not delete any label
    assert result is None


@pytest.mark.asyncio
async def test_check_run_completed_some_in_progress():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
            "status": "completed",
            "conclusion": "cancelled",
        },
        "name": "validate-solutions",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="3")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "number": number,
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                    ],
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {
                    "status": "completed",
                    "conclusion": "cancelled",
                    "name": "validate-solutions",
                },
                {
                    "status": "in_progress",
                    "conclusion": None,
                    "name": "pre-commit",
                },
            ],
        },
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert len(gh.getitem_url) == 2
    assert gh.getitem_url == [search_url, check_run_url]
    assert gh.post_data == []
    assert gh.post_url == []  # does not add any label
    assert gh.delete_url == []  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_passing_no_label():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
        },
        "name": "validate-solutions",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="4")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "number": number,
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                    ],
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {
                    "status": "completed",
                    "conclusion": "success",
                    "name": "validate-solutions",
                },
                {
                    "status": "completed",
                    "conclusion": "skipped",
                    "name": "pre-commit",
                },
            ],
        },
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert len(gh.getitem_url) == 2
    assert gh.getitem_url == [search_url, check_run_url]
    assert gh.post_data == []
    assert gh.post_url == []  # does not add any label
    assert gh.delete_url == []  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_passing_with_label():
    rm_labels_url = f"{labels_url}/{urllib.parse.quote(Label.FAILED_TEST)}"
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
            "status": "completed",
            "conclusion": "action_required",
        },
        "name": "validate-solutions",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="5")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "number": number,
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                        {"name": Label.FAILED_TEST},
                    ],
                    "labels_url": labels_url,
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {
                    "status": "completed",
                    "conclusion": "action_required",
                    "name": "validate-solutions",
                },
                {
                    "status": "completed",
                    "conclusion": "success",
                    "name": "pre-commit",
                },
            ],
        },
    }
    delete = {rm_labels_url: [{"name": "Status: awaiting reviews"}]}
    gh = MockGitHubAPI(getitem=getitem, delete=delete)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert len(gh.getitem_url) == 2
    assert gh.getitem_url == [search_url, check_run_url]
    assert gh.post_url == []
    assert gh.post_data == []  # does not add any label
    assert gh.delete_url[0] == rm_labels_url


@pytest.mark.asyncio
async def test_check_run_completed_failing_no_label():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
        },
        "name": "validate-solutions",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="6")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "number": number,
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                    ],
                    "labels_url": labels_url,
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {
                    "status": "completed",
                    "conclusion": "success",
                    "name": "validate-solutions",
                },
                {
                    "status": "completed",
                    "conclusion": "failure",
                    "name": "pre-commit",
                },
            ],
        },
    }
    post = {
        labels_url: [
            {"name": "Status: awaiting reviews"},
            {"name": Label.FAILED_TEST},
        ]
    }
    gh = MockGitHubAPI(getitem=getitem, post=post)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert len(gh.getitem_url) == 2
    assert gh.getitem_url == [search_url, check_run_url]
    assert gh.delete_url == []  # does not delete any label
    assert gh.post_url[0] == labels_url
    assert gh.post_data[0] == {"labels": [Label.FAILED_TEST]}


@pytest.mark.asyncio
async def test_check_run_completed_failing_with_label():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
            "status": "completed",
            "conclusion": "timed_out",
        },
        "name": "Travis CI - Pull Request",
        "repository": {"full_name": repository},
        "installation": {"id": MOCK_INSTALLATION_ID},
    }
    event = sansio.Event(data, event="check_run", delivery_id="7")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "number": number,
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                        {"name": Label.FAILED_TEST},
                    ],
                    "labels_url": check_run_url,
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {
                    "status": "completed",
                    "conclusion": "timed_out",
                    "name": "Travis CI - Pull Request",
                },
                {
                    "status": "completed",
                    "conclusion": "success",
                    "name": "pre-commit",
                },
            ],
        },
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert len(gh.getitem_url) == 2
    assert gh.getitem_url == [search_url, check_run_url]
    assert gh.post_data == []  # does not add any label
    assert gh.post_url == []
    assert gh.delete_url == []  # does not delete any label
