import os

import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import apps


async def get_access_token(
    gh: gh_aiohttp.GitHubAPI, installation_id: int, cache: cachetools.TTLCache
):
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
    gh: gh_aiohttp.GitHubAPI, sha: str, installation_id: int, cache: cachetools.TTLCache
):
    """Return the pull request object for the given SHA of a commit."""
    installation_access_token = await get_access_token(gh, installation_id, cache)
    prs_for_commit = await gh.getitem(
        f"/search/issues?q=type:pr+repo:TheAlgorithms/Python+sha:{sha}",
        oauth_token=installation_access_token,
    )
    if prs_for_commit["total_count"] > 0:
        # There should only be one
        pr_for_commit = prs_for_commit["items"][0]
        return pr_for_commit
    return None


async def get_check_runs_for_commit(
    gh: gh_aiohttp.GitHubAPI, sha: str, installation_id: int, cache: cachetools.TTLCache
):
    """Return the check runs object for the given SHA of a commit."""
    installation_access_token = await get_access_token(gh, installation_id, cache)
    return await gh.getitem(
        f"/repos/TheAlgorithms/Python/commits/{sha}/check-runs",
        accept="application/vnd.github.v3+json",
        oauth_token=installation_access_token,
    )
