import logging
import os
from typing import Mapping, Tuple

import cachetools
from aiohttp import ClientResponse
from gidgethub import apps
from gidgethub.abc import UTF_8_CHARSET
from gidgethub.aiohttp import GitHubAPI as BaseGitHubAPI

from .log import STATUS_OK, inject_status_color
from .log import logger as main_logger

TOKEN_ENDPOINT = "access_tokens"

# Timed cache for installation access token (1 minute less than an hour)
cache = cachetools.TTLCache(
    maxsize=10, ttl=1 * 59 * 60
)  # type: cachetools.TTLCache[int, str]


class GitHubAPI(BaseGitHubAPI):

    _installation_id: int
    logger: logging.Logger

    LOG_FORMAT = 'api "%(method)s %(path)s %(data)s %(version)s" => %(status)s'

    def __init__(self, installation_id, *args, **kwargs) -> None:
        self._installation_id = installation_id
        self.logger = kwargs.pop("logger", main_logger)
        super().__init__(*args, **kwargs)

    @property
    def headers(self):
        """Return the response headers after it is stored."""
        if hasattr(self, "_headers"):
            return self._headers
        return None

    @headers.setter
    def headers(self, *args, **kwargs):
        raise AttributeError("'headers' property is read-only")

    @property
    async def access_token(self) -> str:
        """Return the installation access token if it is present in the cache else
        create a new token and store it for later use.

        This is a read-only property.
        """
        # Currently, the token lasts for 1 hour.
        # https://docs.github.com/en/developers/apps/differences-between-github-apps-and-oauth-apps#token-based-identification
        # We will store the token with key as installation ID so that the app can be
        # installed in multiple repositories.
        installation_id = self._installation_id
        if installation_id in cache:
            return cache[installation_id]
        data = await apps.get_installation_access_token(
            self,
            installation_id=str(installation_id),
            app_id=os.environ["GITHUB_APP_ID"],
            private_key=os.environ["GITHUB_PRIVATE_KEY"],
        )
        cache[installation_id] = data["token"]
        return cache[installation_id]

    @access_token.setter
    def access_token(self, *args, **kwargs) -> None:
        raise AttributeError("'access_token' property is read-only")

    async def _request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes = b""
    ) -> Tuple[int, Mapping[str, str], bytes]:
        """This is the same method as `gidgethub.aiohttp.GitHubAPI._request` with the
        addition of logging the request-response cycle. No need to cover this function.
        """
        async with self._session.request(
            method, url, headers=headers, data=body
        ) as response:
            self.log(response, body)
            # Let's store the headers for later use.
            self._headers = response.headers
            return response.status, response.headers, await response.read()

    def log(self, response: ClientResponse, body: bytes) -> None:
        """Log the request-response cycle for the GitHub API calls made by the bot.

        The logger information will be useful to know what actions the bot made.
        INFO: All actions taken by the bot.
        ERROR: Unknown error in the API call.
        """
        # We don't want to reveal the `installation_id` from the URL.
        if response.url.name != TOKEN_ENDPOINT:
            inject_status_color(response.status)
            # Comments are too long to be logged.
            if response.url.name == "comments":  # pragma: no cover
                data = "COMMENT"
            else:
                data = body.decode(UTF_8_CHARSET)
            loggerlevel = (
                self.logger.info if response.status in STATUS_OK else self.logger.error
            )
            loggerlevel(
                self.LOG_FORMAT,
                {
                    "method": response.method,
                    # host is always going to be 'api.github.com'.
                    "path": response.url.raw_path_qs,
                    "version": f"{response.url.scheme.upper()}/"
                    f"{response.version.major}.{response.version.minor}",
                    "data": data,
                    "status": f"{response.status}:{response.reason}",
                },
            )
