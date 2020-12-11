import urllib.parse

import pytest
from gidgethub import sansio

from algorithms_keeper import check_runs
from algorithms_keeper.constants import Label

from .utils import (
    MockGitHubAPI,
    check_run_url,
    labels_url,
    number,
    repository,
    search_url,
    sha,
)


@pytest.mark.asyncio
async def test_check_run_not_from_pr_commit():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
        },
        "repository": {"full_name": repository},
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="check_run", delivery_id="2")
    getitem = {
        search_url: {
            "total_count": 0,
            "items": [],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 1
    assert search_url in gh.getitem_url
    assert gh.post_url == []  # does not add any label
    assert gh.post_data == []
    assert gh.delete_url == []  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_some_in_progress():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
        },
        "repository": {"full_name": repository},
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="check_run", delivery_id="3")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [{"labels": [{"name": Label.REVIEW}]}],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "cancelled"},
                {"status": "in_progress", "conclusion": None},
            ],
        },
    }
    gh = MockGitHubAPI(getitem=getitem)
    await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 2
    assert search_url in gh.getitem_url
    assert check_run_url in gh.getitem_url
    assert gh.post_data == []
    assert gh.post_url == []  # does not add any label
    assert gh.delete_url == []  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_passing_no_label():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
        },
        "repository": {"full_name": repository},
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="check_run", delivery_id="4")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [{"labels": [{"name": Label.REVIEW}]}],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "skipped"},
            ],
        },
    }
    gh = MockGitHubAPI(getitem=getitem)
    await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 2
    assert search_url in gh.getitem_url
    assert check_run_url in gh.getitem_url
    assert gh.post_data == []
    assert gh.post_url == []  # does not add any label
    assert gh.delete_url == []  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_passing_with_label():
    remove_labels_url = f"{labels_url}/{urllib.parse.quote(Label.FAILED_TEST)}"
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
        },
        "repository": {"full_name": repository},
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="check_run", delivery_id="5")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "labels": [{"name": Label.FAILED_TEST}],
                    "labels_url": labels_url,
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "action_required"},
                {"status": "completed", "conclusion": "success"},
            ],
        },
    }
    delete = {remove_labels_url: None}
    gh = MockGitHubAPI(getitem=getitem, delete=delete)
    await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 2
    assert search_url in gh.getitem_url
    assert check_run_url in gh.getitem_url
    assert gh.post_url == []
    assert gh.post_data == []  # does not add any label
    assert remove_labels_url in gh.delete_url


@pytest.mark.asyncio
async def test_check_run_completed_failing_no_label():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
        },
        "repository": {"full_name": repository},
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="check_run", delivery_id="6")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [
                {
                    "labels": [{"name": Label.REVIEW}],
                    "labels_url": labels_url,
                }
            ],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "failure"},
            ],
        },
    }
    post = {labels_url: None}
    gh = MockGitHubAPI(getitem=getitem, post=post)
    await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 2
    assert search_url in gh.getitem_url
    assert check_run_url in gh.getitem_url
    assert gh.delete_url == []  # does not delete any label
    assert labels_url in gh.post_url
    assert {"labels": [Label.FAILED_TEST]} in gh.post_data


@pytest.mark.asyncio
async def test_check_run_completed_failing_with_label():
    data = {
        "action": "completed",
        "check_run": {
            "head_sha": sha,
        },
        "repository": {"full_name": repository},
        "installation": {"id": number},
    }
    event = sansio.Event(data, event="check_run", delivery_id="7")
    getitem = {
        search_url: {
            "total_count": 1,
            "items": [{"labels": [{"name": Label.FAILED_TEST}]}],
        },
        check_run_url: {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "timed_out"},
                {"status": "completed", "conclusion": "success"},
            ],
        },
    }
    gh = MockGitHubAPI(getitem=getitem)
    await check_runs.router.dispatch(event, gh)
    assert len(gh.getitem_url) == 2
    assert search_url in gh.getitem_url
    assert check_run_url in gh.getitem_url
    assert gh.post_data == []  # does not add any label
    assert gh.post_url == []
    assert gh.delete_url == []  # does not delete any label
