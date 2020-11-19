"""Utility module for the bot

This is the only module which will make all the API calls to GitHub. None of the event
modules will make any API calls because we want to keep the logic separated. API calls
logic will be handled in this module and event logic will be handled in their respective
event modules.

All functions must have only two positional arguments:
`gh`: This is the GithubAPI object used to make all the API calls.
`installation_id`: The installation ID for the GitHub app (bot).

The rest of the arguments must be keyword-only arguments. This is done to
maintain consistency throughout the module and improve readability in files
that uses all the given functions.
"""
import base64
import os
import urllib.parse
from typing import Any, Dict, List, Optional, Union

import cachetools
from gidgethub import apps
from gidgethub.aiohttp import GitHubAPI

# Timed cache for installation access token (1 hour)
cache = cachetools.TTLCache(maxsize=1, ttl=3600)  # type: cachetools.TTLCache[str, str]


async def get_access_token(gh: GitHubAPI, installation_id: int) -> str:
    """Return the installation access token if it is present in the cache else
    create a new token and store it for later use.

    Currently, the token lasts for 1 hour.
    https://docs.github.com/en/developers/apps/differences-between-github-apps-and-oauth-apps#token-based-identification
    """
    if "access_token" in cache:
        return cache["access_token"]
    data = await apps.get_installation_access_token(
        gh,
        installation_id=str(installation_id),
        app_id=os.environ.get("GITHUB_APP_ID"),
        private_key=os.environ.get("GITHUB_PRIVATE_KEY"),
    )
    cache["access_token"] = data["token"]
    return cache["access_token"]


async def get_pr_for_commit(
    gh: GitHubAPI, installation_id: int, *, sha: str, repository: str
) -> Optional[Any]:
    """Return the issue object, relative to the pull request, for the given SHA
    of a commit.

    GitHub's REST API v3 considers every pull request an issue, but not every issue
    is a pull request. This means when we search for a pull request, we get the issue
    object with the pull request url information in it as `issue["pull_request"]`.
    """
    installation_access_token = await get_access_token(gh, installation_id)
    data = await gh.getitem(
        f"/search/issues?q=type:pr+state:open+draft:false+repo:{repository}+sha:{sha}",
        oauth_token=installation_access_token,
    )
    if data["total_count"] > 0:
        # There should only be one
        return data["items"][0]
    return None


async def get_check_runs_for_commit(
    gh: GitHubAPI, installation_id: int, *, sha: str, repository: str
) -> Any:
    """Return the check runs object for the given SHA of a commit."""
    installation_access_token = await get_access_token(gh, installation_id)
    return await gh.getitem(
        f"/repos/{repository}/commits/{sha}/check-runs",
        oauth_token=installation_access_token,
    )


async def add_label_to_pr_or_issue(
    gh: GitHubAPI,
    installation_id: int,
    *,
    label: Union[str, List[str]],
    pr_or_issue: Dict[str, Any],
) -> None:
    """Add the given label(s) to the pull request or issue provided.

    `label` can be either one label (string) or a list of labels.

    The issue object contains the labels url in it but for pull request object we will
    construct it using `issue_url`. This is done to make this function versatile so
    that we can add a label to either the issue or pull request.
    """
    installation_access_token = await get_access_token(gh, installation_id)
    labels_url = (
        pr_or_issue["labels_url"]
        if "labels_url" in pr_or_issue
        else pr_or_issue["issue_url"] + "/labels"
    )
    await gh.post(
        labels_url,
        data={"labels": [label] if isinstance(label, str) else label},
        oauth_token=installation_access_token,
    )


async def remove_label_from_pr_or_issue(
    gh: GitHubAPI,
    installation_id: int,
    *,
    label: Union[str, List[str]],
    pr_or_issue: Dict[str, Any],
) -> None:
    """Remove the given label(s) from pull request or issue provided.

    `label` can be either one label (string) or a list of labels.

    The issue object contains the labels url in it but for pull request object we will
    construct it using the issue_url. This is done to make this function versatile so
    that we can remove a label from either the issue or pull request.
    """
    installation_access_token = await get_access_token(gh, installation_id)
    labels_url = (
        pr_or_issue["labels_url"]
        if "labels_url" in pr_or_issue
        else pr_or_issue["issue_url"] + "/labels"
    )
    label_list = [label] if isinstance(label, str) else label
    # We can only remove labels one at a time or all (every label in the pull request
    # or issue) at once.
    for label in label_list:
        parse_label = urllib.parse.quote(label)
        await gh.delete(
            f"{labels_url}/{parse_label}",
            oauth_token=installation_access_token,
        )


async def get_total_open_prs(
    gh: GitHubAPI,
    installation_id: int,
    *,
    repository: str,
    user_login: Optional[str] = None,
    count: Optional[bool] = True,
) -> Any:
    """Return the total number of open pull requests in the repository.

    If the `user_login` parameter is given, then return the total number of open
    pull request by that user in the repository.

    If the `count` parameter is `False`, it returns the list of pull request
    numbers instead.

    For GitHub's REST API v3, issues and pull requests are the same so
    `repository["open_issues_count"]` returns the total number of open
    issues and pull requests. As we only want the pull request count,
    we can make a search API call for open pull requests.
    """
    installation_access_token = await get_access_token(gh, installation_id)
    search_url = f"/search/issues?q=type:pr+state:open+repo:{repository}"
    if user_login is not None:
        search_url += f"+author:{user_login}"
    if count is False:
        pr_numbers = []
        async for pull in gh.getiter(search_url, oauth_token=installation_access_token):
            pr_numbers.append(pull["number"])
        return pr_numbers
    data = await gh.getitem(search_url, oauth_token=installation_access_token)
    return data["total_count"]


async def add_comment_to_pr_or_issue(
    gh: GitHubAPI, installation_id: int, *, comment: str, pr_or_issue: Dict[str, Any]
) -> None:
    """Add a comment to the given pull request or issue object."""
    installation_access_token = await get_access_token(gh, installation_id)
    await gh.post(
        pr_or_issue["comments_url"],
        data={"body": comment},
        oauth_token=installation_access_token,
    )


async def close_pr_or_issue(
    gh: GitHubAPI,
    installation_id: int,
    *,
    comment: str,
    pr_or_issue: Dict[str, Any],
    label: Optional[Union[str, List[str]]] = None,
) -> None:
    """Close the given pull request or issue with a comment and an optional label.
    If it is a pull request then dismiss all the requested reviews from it as well.

    As everything is going to be done by the bot, we will make comments compulsory
    so as to know why was this pull request or issue closed.
    """
    installation_access_token = await get_access_token(gh, installation_id)
    await add_comment_to_pr_or_issue(
        gh, installation_id, comment=comment, pr_or_issue=pr_or_issue
    )
    if label is not None:
        await add_label_to_pr_or_issue(
            gh, installation_id, label=label, pr_or_issue=pr_or_issue
        )
    await gh.patch(
        pr_or_issue["url"],
        data={"state": "closed"},
        oauth_token=installation_access_token,
    )
    try:
        # The review requests will be coming from the CODEOWNERS file
        if pr_or_issue["requested_reviewers"]:
            await remove_requested_reviewers_from_pr(
                gh, installation_id, pull_request=pr_or_issue
            )
    except KeyError:
        pass


async def remove_requested_reviewers_from_pr(
    gh: GitHubAPI, installation_id: int, *, pull_request: Dict[str, Any]
) -> None:
    """Remove all the requested reviewers from the given pull request."""
    installation_access_token = await get_access_token(gh, installation_id)
    await gh.delete(
        pull_request["url"] + "/requested_reviewers",
        data={
            "reviewers": [
                reviewer["login"] for reviewer in pull_request["requested_reviewers"]
            ]
        },
        oauth_token=installation_access_token,
    )


async def get_pr_files(
    gh: GitHubAPI, installation_id: int, *, pull_request: Dict[str, Any]
) -> List[Dict[str, str]]:
    """Return the list of files data from a given pull request.

    The data will include `filename` and `contents_url`. The `contents_url` will be
    used to download and parse the Python code and check for tests and type hints.
    """
    installation_access_token = await get_access_token(gh, installation_id)
    files = []
    async for data in gh.getiter(
        pull_request["url"] + "/files", oauth_token=installation_access_token
    ):
        files.append(
            {"filename": data["filename"], "contents_url": data["contents_url"]}
        )
    return files


async def get_file_content(
    gh: GitHubAPI, installation_id: int, *, file: Dict[str, str]
) -> bytes:
    """Return the file content decoded into Python bytes object."""
    installation_access_token = await get_access_token(gh, installation_id)
    data = await gh.getitem(file["contents_url"], oauth_token=installation_access_token)
    return base64.decodebytes(data["content"].encode())
