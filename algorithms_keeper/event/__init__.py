from gidgethub.routing import Router

from algorithms_keeper.event.check_run import check_run_router
from algorithms_keeper.event.commands import commands_router
from algorithms_keeper.event.installation import installation_router
from algorithms_keeper.event.pull_request import pull_request_router

main_router: Router = Router(
    check_run_router,
    commands_router,
    installation_router,
    pull_request_router,
)

__all__ = ["main_router"]
