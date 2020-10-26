import os

import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import apps

# Timed cache for installation access token (1 hour)
cache = cachetools.TTLCache(maxsize=500, ttl=3600)  # type: cachetools.TTLCache


async def get_access_token(gh: gh_aiohttp.GitHubAPI, installation_id: int):
    """Get the installation access token after it expires

    Currently, the token lasts for 1 hour so we will give the
    time to live parameter in TTLCache 3600 seconds.
    https://docs.github.com/en/developers/apps/differences-between-github-apps-and-oauth-apps#token-based-identification
    """
    if "access_token" in cache:
        return cache["access_token"]
    installation_access_token = await apps.get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=os.environ.get("GITHUB_APP_ID"),
        private_key=os.environ.get("GITHUB_PRIVATE_KEY"),
    )
    cache["access_token"] = installation_access_token["token"]
    return cache["access_token"]


async def get_pr_for_commit(
    sha: str, gh: gh_aiohttp.GitHubAPI, installation_id: int, repository: str
):
    """Return the pull request object for the given SHA of a commit."""
    installation_access_token = await get_access_token(gh, installation_id)
    prs_for_commit = await gh.getitem(
        f"/search/issues?q=type:pr+repo:{repository}+sha:{sha}",
        oauth_token=installation_access_token,
    )
    if prs_for_commit["total_count"] > 0:
        # There should only be one
        pr_for_commit = prs_for_commit["items"][0]
        return pr_for_commit
    return None


async def get_check_runs_for_commit(
    sha: str, gh: gh_aiohttp.GitHubAPI, installation_id: int, repository: str
):
    """Return the check runs object for the given SHA of a commit."""
    installation_access_token = await get_access_token(gh, installation_id)
    return await gh.getitem(
        f"/repos/{repository}/commits/{sha}/check-runs",
        oauth_token=installation_access_token,
    )


async def get_pull_request(
    pr_number: int,
    gh: gh_aiohttp.GitHubAPI,
    installation_id: int,
    repository: str,
):
    installation_access_token = await get_access_token(gh, installation_id)
    return await gh.getitem(
        f"/repos/{repository}/pulls/{pr_number}",
        oauth_token=installation_access_token,
    )


async def add_label_to_pr(
    label: str,
    pr_number: int,
    gh: gh_aiohttp.GitHubAPI,
    installation_id: int,
    repository: str,
):
    """Add the given labels to the pull request number provided."""
    installation_access_token = await get_access_token(gh, installation_id)
    pr = await get_pull_request(pr_number, gh, installation_id, repository)
    issue_url = pr["issue_url"]
    await gh.post(
        f"{issue_url}/labels",
        data={"labels": label},
        oauth_token=installation_access_token,
    )
