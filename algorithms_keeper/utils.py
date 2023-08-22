"""Utility module for the bot

This is the only module which will make all the API calls to GitHub. None of the event
modules will make any API calls because we want to keep the logic separated. API calls
logic will be handled in this module and event logic will be handled in their respective
event modules.

All functions must have only one positional arguments:
`gh`: This is the GithubAPI object used to make all the API calls.

The rest of the arguments must be keyword-only arguments. This is done to
maintain consistency throughout the module and improve readability in files
that uses all the given functions.
"""
import urllib.parse
from base64 import b64decode
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.constants import PR_REVIEW_BODY


@dataclass(frozen=True)
class File:
    # `name` is the entire path from repository root to the file in ``str``.
    # This is different from ``pathlib.PurePath.name`` where the latter gives the
    # `basename` of the path.
    name: str

    # A ``pathlib.Path`` object which represents the `name` in PathLike format which
    # can be used to check extension and filename.
    path: Path

    # The `contents_url` value of the file object we get for all the pull request files.
    # This can be used to get the file content directly from GitHub instead of cloning
    # the repository on the server.
    contents_url: str

    # The status of the file, can be either "added" or "modified". This will be used to
    # determine whether a PR is of type enhancement.
    status: str


async def get_pr_for_commit(
    gh: GitHubAPI, *, sha: str, repository: str
) -> Optional[Any]:
    """Return the issue object, relative to the pull request, for the given SHA
    of a commit.

    GitHub's REST API v3 considers every pull request an issue, but not every issue
    is a pull request. This means when we search for a pull request, we get the issue
    object with the pull request url information in it as `issue["pull_request"]`.
    """
    data = await gh.getitem(
        f"/search/issues?q=type:pr+state:open+draft:false+repo:{repository}+sha:{sha}",
        oauth_token=await gh.access_token,
    )
    if data["total_count"] > 0:
        # There should only be one
        return data["items"][0]
    return None


async def get_check_runs_for_commit(gh: GitHubAPI, *, sha: str, repository: str) -> Any:
    """Return the check runs object for the given SHA of a commit."""
    return await gh.getitem(
        f"/repos/{repository}/commits/{sha}/check-runs",
        oauth_token=await gh.access_token,
    )


async def add_label_to_pr_or_issue(
    gh: GitHubAPI,
    *,
    label: Union[str, list[str]],
    pr_or_issue: Mapping[str, Any],
) -> None:
    """Add the given label(s) to the pull request or issue provided.

    `label` can be either one label (string) or a list of labels.

    The issue object contains the labels url in it but for pull request object we will
    construct it using `issue_url`. This is done to make this function versatile so
    that we can add a label to either the issue or pull request.
    """
    labels_url = (
        pr_or_issue["labels_url"]
        if "labels_url" in pr_or_issue
        else pr_or_issue["issue_url"] + "/labels"
    )
    await gh.post(
        labels_url,
        data={"labels": [label] if isinstance(label, str) else label},
        oauth_token=await gh.access_token,
    )


async def remove_label_from_pr_or_issue(
    gh: GitHubAPI,
    *,
    label: Union[str, list[str]],
    pr_or_issue: Mapping[str, Any],
) -> None:
    """Remove the given label(s) from pull request or issue provided.

    `label` can be either one label (string) or a list of labels.

    The issue object contains the labels url in it but for pull request object we will
    construct it using the issue_url. This is done to make this function versatile so
    that we can remove a label from either the issue or pull request.
    """
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
            oauth_token=await gh.access_token,
        )


async def get_user_open_pr_numbers(
    gh: GitHubAPI, *, repository: str, user_login: str
) -> list[int]:
    """Return the user's open pull request numbers in the given repository.

    For GitHub's REST API v3, issues and pull requests are the same so
    `repository["open_issues_count"]` returns the total number of open
    issues and pull requests. As we only want the pull request count,
    we can make a search API call for open pull requests.
    """
    search_url = (
        f"/search/issues?q=type:pr+state:open+repo:{repository}+author:{user_login}"
    )
    pr_numbers = []
    async for pull in gh.getiter(search_url, oauth_token=await gh.access_token):
        pr_numbers.append(pull["number"])  # noqa: PERF401
    return pr_numbers


async def add_comment_to_pr_or_issue(
    gh: GitHubAPI, *, comment: str, pr_or_issue: Mapping[str, Any]
) -> None:
    """Add a comment to the given pull request or issue object."""
    await gh.post(
        pr_or_issue["comments_url"],
        data={"body": comment},
        oauth_token=await gh.access_token,
    )


async def close_pr_or_issue(
    gh: GitHubAPI,
    *,
    comment: str,
    pr_or_issue: Mapping[str, Any],
    label: Optional[Union[str, list[str]]] = None,
) -> None:
    """Close the given pull request or issue with a comment and an optional label.
    If it is a pull request then dismiss all the requested reviews from it as well.

    As everything is going to be done by the bot, we will make comments compulsory
    so as to know why was this pull request or issue closed.
    """
    await add_comment_to_pr_or_issue(gh, comment=comment, pr_or_issue=pr_or_issue)
    if label is not None:
        await add_label_to_pr_or_issue(gh, label=label, pr_or_issue=pr_or_issue)
    await gh.patch(
        pr_or_issue["url"],
        data={"state": "closed"},
        oauth_token=await gh.access_token,
    )
    try:
        # The review requests will be coming from the CODEOWNERS file
        if pr_or_issue["requested_reviewers"]:
            await remove_requested_reviewers_from_pr(gh, pull_request=pr_or_issue)
    except KeyError:
        pass


async def remove_requested_reviewers_from_pr(
    gh: GitHubAPI, *, pull_request: Mapping[str, Any]
) -> None:
    """Remove all the requested reviewers from the given pull request."""
    await gh.delete(
        pull_request["url"] + "/requested_reviewers",
        data={
            "reviewers": [
                reviewer["login"] for reviewer in pull_request["requested_reviewers"]
            ]
        },
        oauth_token=await gh.access_token,
    )


async def get_pr_files(gh: GitHubAPI, *, pull_request: Mapping[str, Any]) -> list[File]:
    """Return the list of files data from a given pull request.

    The data will include `filename` and `contents_url`. The `contents_url` will be
    used to download and parse the Python code and check for tests and type hints.
    """
    files = []
    async for data in gh.getiter(
        pull_request["url"] + "/files", oauth_token=await gh.access_token
    ):
        files.append(  # noqa: PERF401
            File(
                data["filename"],
                Path(data["filename"]),
                data["contents_url"],
                data["status"],
            )
        )
    return files


async def get_file_content(gh: GitHubAPI, *, file: File) -> bytes:
    """Return the file content decoded into Python bytes object."""
    data = await gh.getitem(file.contents_url, oauth_token=await gh.access_token)
    return b64decode(data["content"])


async def create_pr_review(
    gh: GitHubAPI, *, pull_request: Mapping[str, Any], comments: list[dict[str, Any]]
) -> None:
    """Submit a comment review for the given pull request.

    `comments` is a list of ``parser.record.ReviewComment`` as dictionary which
    represents the pull request review comment.
    """
    await gh.post(
        pull_request["url"] + "/reviews",
        data={
            "commit_id": pull_request["head"]["sha"],
            "body": PR_REVIEW_BODY,
            "event": "COMMENT",
            "comments": comments,
        },
        accept="application/vnd.github.comfort-fade-preview+json",
        oauth_token=await gh.access_token,
    )


async def add_reaction(
    gh: GitHubAPI, *, reaction: str, comment: Mapping[str, Any]
) -> None:
    """Add the given ``reaction`` to the provided ``comment``."""
    await gh.post(
        comment["url"] + "/reactions",
        data={"content": reaction},
        accept="application/vnd.github.squirrel-girl-preview+json",
        oauth_token=await gh.access_token,
    )


async def get_pr_for_issue(gh: GitHubAPI, *, issue: Mapping[str, Any]) -> Any:
    """Return the pull request object for the given issue object."""
    return await gh.getitem(
        issue["pull_request"]["url"], oauth_token=await gh.access_token
    )


async def update_pr(gh: GitHubAPI, *, pull_request: Mapping[str, Any]) -> Any:
    """Get the updated pull request object for the given pull request."""
    return await gh.getitem(pull_request["url"], oauth_token=await gh.access_token)
