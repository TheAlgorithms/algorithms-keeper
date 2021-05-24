import logging
from typing import Any

from gidgethub import routing
from gidgethub.sansio import Event

from algorithms_keeper import utils
from algorithms_keeper.api import GitHubAPI

workflow_router = routing.Router()

logger = logging.getLogger(__package__)


@workflow_router.register("workflow_run", action="requested")
async def approve_workflow_run(
    event: Event, gh: GitHubAPI, *args: Any, **kwargs: Any
) -> None:
    """Approve a workflow run from a first-time contributor."""
    workflow_run = event.data["workflow_run"]

    if workflow_run["conclusion"] != "action_required":
        return None

    pull_request = await utils.get_pr_for_workflow_run(gh, workflow_run=workflow_run)
    if pull_request is None:
        return None

    logger.info(
        "Approving the workflow %d (PR #%d)",
        workflow_run["id"],
        pull_request["number"],
    )
    await utils.approve_workflow_run(gh, workflow_run=workflow_run)
