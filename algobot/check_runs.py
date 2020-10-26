from typing import Any

import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing, sansio

from . import utils

router = routing.Router()

FAILURE_LABEL = "Status: Tests are failing"


@router.register("check_run", action="completed")
async def check_run_completed(
    gh: gh_aiohttp.GitHubAPI,
    event: sansio.Event,
    cache: cachetools.TTLCache,
    *args: Any,
    **kwargs: Any,
):
    """Handler for check run completed event.

    We will get the event payload everytime a check run is completed which is
    a lot of times for a single commit. So, the `if` statement makes sure we
    execute the block only when the last check run is completed.
    """
    commit_sha = event.data["check_run"]["head_sha"]
    installation_id = event.data["installation"]["id"]

    pr_for_commit = await utils.get_pr_for_commit(
        gh, commit_sha, installation_id, cache
    )
    check_runs = await utils.get_check_runs_for_commit(
        gh, commit_sha, installation_id, cache
    )

    all_check_run_status = [
        check_run["status"] for check_run in check_runs["check_runs"]
    ]
    all_check_run_conclusions = [
        check_run["conclusion"] for check_run in check_runs["check_runs"]
    ]

    if (
        "in_progress" not in all_check_run_status
        and "queued" not in all_check_run_status
    ):  # wait until all check runs are completed
        pr_number = pr_for_commit["number"]
        if any(
            element in [None, "failure", "timed_out"]
            for element in all_check_run_conclusions
        ):
            print(f"Failure detected in PR {pr_number}")
