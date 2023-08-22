import pytest
from gidgethub.sansio import Event

from algorithms_keeper.constants import GREETING_COMMENT
from algorithms_keeper.event.installation import installation_router

from .utils import (
    ExpectedData,
    MockGitHubAPI,
    issue_path,
    issue_url,
    number,
    parametrize_id,
    repository,
    user,
)

FILLED_GREETING_COMMENT = GREETING_COMMENT.format(login=user)


# Reminder: ``Event.delivery_id`` is used as a short description for the respective
# test case and as a way to id the specific test case in the parametrized group.
@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "event, gh, expected",
    (
        # Installation was created on a repository.
        (
            Event(
                data={
                    "action": "created",
                    "installation": {"id": number},
                    "repositories": [{"full_name": repository}],
                    "sender": {"login": user},
                },
                event="installation",
                delivery_id="installation_created",
            ),
            MockGitHubAPI(post={issue_path: {"url": issue_url}}),
            ExpectedData(
                post_url=[issue_path],
                post_data=[
                    {
                        "title": "Installation successful!",
                        "body": FILLED_GREETING_COMMENT,
                    }
                ],
                patch_url=[issue_url],
                patch_data=[{"state": "closed"}],
            ),
        ),
        # Installation was added on a repository.
        (
            Event(
                data={
                    "action": "added",
                    "installation": {"id": number},
                    "repositories_added": [{"full_name": repository}],
                    "sender": {"login": user},
                },
                event="installation_repositories",
                delivery_id="installation_added",
            ),
            MockGitHubAPI(post={issue_path: {"url": issue_url}}),
            ExpectedData(
                post_url=[issue_path],
                post_data=[
                    {
                        "title": "Installation successful!",
                        "body": FILLED_GREETING_COMMENT,
                    }
                ],
                patch_url=[issue_url],
                patch_data=[{"state": "closed"}],
            ),
        ),
    ),
    ids=parametrize_id,
)
async def test_installations(
    event: Event, gh: MockGitHubAPI, expected: ExpectedData
) -> None:
    await installation_router.dispatch(event, gh)
    assert gh == expected
