import pytest
from gidgethub.sansio import Event

from algorithms_keeper.constants import EMPTY_ISSUE_BODY_COMMENT, Label
from algorithms_keeper.event.issues import issues_router

from .utils import (
    ExpectedData,
    MockGitHubAPI,
    comments_url,
    html_issue_url,
    issue_url,
    labels_url,
    parametrize_id,
    user,
)

FILLED_EMPTY_ISSUE_BODY_COMMENT = EMPTY_ISSUE_BODY_COMMENT.format(user_login=user)


# Reminder: ``Event.delivery_id`` is used as a short description for the respective
# test case and as a way to id the specific test case in the parametrized group.
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event, gh, expected",
    (
        # Issue opened with an empty description so label it invalid, comment and
        # close the issue.
        (
            Event(
                data={
                    "action": "opened",
                    "issue": {
                        "url": issue_url,
                        "comments_url": comments_url,
                        "labels_url": labels_url,
                        "user": {"login": user},
                        "body": "",
                        "html_url": html_issue_url,
                    },
                },
                event="issues",
                delivery_id="empty_description",
            ),
            MockGitHubAPI(),
            ExpectedData(
                post_url=[comments_url, labels_url],
                post_data=[
                    {"body": FILLED_EMPTY_ISSUE_BODY_COMMENT},
                    {"labels": [Label.INVALID]},
                ],
                patch_url=[issue_url],
                patch_data=[{"state": "closed"}],
            ),
        ),
        # Issue opened with non empty description, so do nothing.
        (
            Event(
                data={
                    "action": "opened",
                    "issue": {
                        "url": issue_url,
                        "comments_url": comments_url,
                        "labels_url": labels_url,
                        "user": {"login": user},
                        "body": "There is one typo in test.py",
                        "html_url": html_issue_url,
                    },
                },
                event="issues",
                delivery_id="non_empty_description",
            ),
            MockGitHubAPI(),
            ExpectedData(),
        ),
    ),
    ids=parametrize_id,
)
async def test_issues(event, gh, expected):
    await issues_router.dispatch(event, gh)
    assert gh == expected
