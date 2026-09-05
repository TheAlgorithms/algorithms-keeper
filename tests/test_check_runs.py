import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import quote

import pytest
from gidgethub import BadRequest
from gidgethub.sansio import Event

from algorithms_keeper.constants import Label
from algorithms_keeper.event.check_run import check_run_router

from .utils import (
    ExpectedData,
    MockGitHubAPI,
    check_run_url,
    labels_url,
    parametrize_id,
    repository,
    search_url,
    sha,
)


# Reminder: ``Event.delivery_id`` is used as a short description for the respective
# test case and as a way to id the specific test case in the parametrized group.
@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "event, gh, expected",
    (
        # Check run completed from a commit which does not belong to a pull request.
        (
            Event(
                data={
                    "action": "completed",
                    "check_run": {
                        "head_sha": sha,
                    },
                    "repository": {"full_name": repository},
                },
                event="check_run",
                delivery_id="commit_not_from_pr",
            ),
            MockGitHubAPI(
                getitem={
                    search_url: {
                        "total_count": 0,
                        "items": [],
                    }
                }
            ),
            ExpectedData(getitem_url=[search_url]),
        ),
        # Check run completed but some of the other checks are in progress.
        (
            Event(
                data={
                    "action": "completed",
                    "check_run": {
                        "head_sha": sha,
                    },
                    "repository": {"full_name": repository},
                },
                event="check_run",
                delivery_id="completed_some_in_progress",
            ),
            MockGitHubAPI(
                getitem={
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
            ),
            ExpectedData(getitem_url=[search_url, check_run_url]),
        ),
        # Check run completed and it's a success, there are no ``FAILED_TEST`` label on
        # the pull request, so no action taken.
        (
            Event(
                data={
                    "action": "completed",
                    "check_run": {
                        "head_sha": sha,
                    },
                    "repository": {"full_name": repository},
                },
                event="check_run",
                delivery_id="completed_passing_no_label",
            ),
            MockGitHubAPI(
                getitem={
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
            ),
            ExpectedData(getitem_url=[search_url, check_run_url]),
        ),
        # Check run completed and it's a success, there is the ``FAILED_TEST`` label on
        # the pull request, so remove it.
        (
            Event(
                data={
                    "action": "completed",
                    "check_run": {
                        "head_sha": sha,
                    },
                    "repository": {"full_name": repository},
                },
                event="check_run",
                delivery_id="completed_passing_with_label",
            ),
            MockGitHubAPI(
                getitem={
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
            ),
            ExpectedData(
                getitem_url=[search_url, check_run_url],
                delete_url=[f"{labels_url}/{quote(Label.FAILED_TEST)}"],
            ),
        ),
        # Check run completed and it's a failure, there is no ``FAILED_TEST`` label on
        # the pull request, so add it.
        (
            Event(
                data={
                    "action": "completed",
                    "check_run": {
                        "head_sha": sha,
                    },
                    "repository": {"full_name": repository},
                },
                event="check_run",
                delivery_id="completed_failing_no_label",
            ),
            MockGitHubAPI(
                getitem={
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
            ),
            ExpectedData(
                getitem_url=[search_url, check_run_url],
                post_url=[labels_url],
                post_data=[{"labels": [Label.FAILED_TEST]}],
            ),
        ),
        # Check run completed and it's a failure, there is ``FAILED_TEST`` label on
        # the pull request, so don't do anything.
        (
            Event(
                data={
                    "action": "completed",
                    "check_run": {
                        "head_sha": sha,
                    },
                    "repository": {"full_name": repository},
                },
                event="check_run",
                delivery_id="completed_failing_with_label",
            ),
            MockGitHubAPI(
                getitem={
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
            ),
            ExpectedData(getitem_url=[search_url, check_run_url]),
        ),
    ),
    ids=parametrize_id,
)
async def test_check_run(
    event: Event, gh: MockGitHubAPI, expected: ExpectedData
) -> None:
    await check_run_router.dispatch(event, gh)
    assert gh == expected


@pytest.mark.asyncio()
async def test_concurrent_check_runs_remove_same_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gh = MockGitHubAPI(
        getitem={
            search_url: {
                "total_count": 1,
                "items": [
                    {"labels": [{"name": Label.FAILED_TEST}], "labels_url": labels_url}
                ],
            },
            check_run_url: {
                "check_runs": [{"status": "completed", "conclusion": "success"}],
            },
        }
    )
    deleted = False
    both_deleting = asyncio.Event()

    async def delete_label(url: str, **kwargs: Any) -> None:
        nonlocal deleted
        # Both handlers have read the same label snapshot before either deletes it.
        if delete.await_count == 2:
            both_deleting.set()
        await asyncio.wait_for(both_deleting.wait(), timeout=5)
        if deleted:
            raise BadRequest(HTTPStatus.NOT_FOUND, "Label does not exist")
        deleted = True

    delete = AsyncMock(side_effect=delete_label)
    monkeypatch.setattr(gh, "delete", delete)
    events = [
        Event(
            data={
                "action": "completed",
                "repository": {"full_name": repository},
                "check_run": {"id": check_id, "head_sha": sha},
            },
            event="check_run",
            delivery_id=f"completed-check-{check_id}",
        )
        for check_id in range(2)
    ]

    await asyncio.gather(*(check_run_router.dispatch(event, gh) for event in events))

    assert deleted
    assert delete.await_count == 2
