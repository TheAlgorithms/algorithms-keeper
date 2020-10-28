import pytest
from _pytest.monkeypatch import MonkeyPatch
from gidgethub import apps, sansio

from algobot import check_runs
from algobot.check_runs import FAILURE_LABEL

from .utils import MOCK_INSTALLATION_ID, MockGitHubAPI, mock_return


def setup_module(module, monkeypatch=MonkeyPatch()):
    """Monkeypatch for this module to store the MOCK_TOKEN in cache.

    We cannot use `pytest.fixture(scope="module")` as `monkeypatch` fixture
    only works at function level (this is a module level setup function),
    so we will directly use the MonkeyPatch class where the fixture is
    generated from and pass it as the default argument to this function.

    This will only be executed once in this module, storing the token in the
    cache for later use.
    """
    monkeypatch.setattr(apps, "get_installation_access_token", mock_return)


@pytest.mark.asyncio
async def test_check_run_created():
    repository = "TheAlgorithms/Python"
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


@pytest.mark.asyncio
async def test_check_run_not_from_pr_commit():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
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
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
            "total_count": 0,
            "incomplete_results": False,
            "items": [],
        }
    }
    gh = MockGitHubAPI(getitem=getitem)
    result = await check_runs.router.dispatch(event, gh)
    assert gh.getitem_url == f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}"
    assert result is None


@pytest.mark.asyncio
async def test_check_run_completed_some_in_progress():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
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
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 3378,
                    "title": "Create GitHub action only for Project Euler",
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                    ],
                }
            ],
        },
        f"/repos/{repository}/commits/{sha}/check-runs": {
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
    assert gh.post_data is None  # does not add any label
    assert gh.post_url is None
    assert gh.delete_url is None  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_passing_no_label():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
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
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 3378,
                    "title": "Create GitHub action only for Project Euler",
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                    ],
                }
            ],
        },
        f"/repos/{repository}/commits/{sha}/check-runs": {
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
    assert gh.post_data is None  # does not add any label
    assert gh.post_url is None
    assert gh.delete_url is None  # does not delete any label


@pytest.mark.asyncio
async def test_check_run_completed_passing_with_label():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
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
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 3378,
                    "title": "Create GitHub action only for Project Euler",
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                        {"name": FAILURE_LABEL},
                    ],
                }
            ],
        },
        f"/repos/{repository}/commits/{sha}/check-runs": {
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
    delete = [{"name": "Status: awaiting reviews"}]
    gh = MockGitHubAPI(getitem=getitem, delete=delete)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert gh.post_data is None  # does not add any label
    assert (
        gh.delete_url
        == f"/repos/{repository}/issues/3378/labels/Status%3A%20Tests%20are%20failing"
    )


@pytest.mark.asyncio
async def test_check_run_completed_failing_no_label():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
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
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 3378,
                    "title": "Create GitHub action only for Project Euler",
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                    ],
                }
            ],
        },
        f"/repos/{repository}/commits/{sha}/check-runs": {
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
    post = [
        {"name": "Status: awaiting reviews"},
        {"name": FAILURE_LABEL},
    ]
    gh = MockGitHubAPI(getitem=getitem, post=post)
    result = await check_runs.router.dispatch(event, gh)
    assert result is None
    assert gh.delete_url is None  # does not delete any label
    assert gh.post_url == f"/repos/{repository}/issues/3378/labels"
    assert gh.post_data == {"labels": [FAILURE_LABEL]}


@pytest.mark.asyncio
async def test_check_run_completed_failing_with_label():
    sha = "a06212064d8e1c349c75c5ea4568ecf155368c21"
    repository = "TheAlgorithms/Python"
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
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 3378,
                    "title": "Create GitHub action only for Project Euler",
                    "state": "open",
                    "labels": [
                        {"name": "Status: awaiting reviews"},
                        {"name": FAILURE_LABEL},
                    ],
                }
            ],
        },
        f"/repos/{repository}/commits/{sha}/check-runs": {
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
    assert gh.post_data is None  # does not add any label
    assert gh.post_url is None
    assert gh.delete_url is None  # does not delete any label
