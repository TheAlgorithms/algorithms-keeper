import logging
import os
from typing import Any, Mapping, MutableMapping

from aiohttp import ClientResponse
from cachetools import TTLCache
from gidgethub import apps
from gidgethub.abc import UTF_8_CHARSET
from gidgethub.aiohttp import GitHubAPI as BaseGitHubAPI

# Timed token_cache for installation access token (1 minute less than an hour)
token_cache: MutableMapping[int, str] = TTLCache(maxsize=10, ttl=1 * 59 * 60)

# From `gidgethub.sansio.decipher_response()`
# From `gidgethub.abc._request()#113`
STATUS_OK: tuple[int, int, int, int] = (200, 201, 204, 304)

logger = logging.getLogger(__package__)


def _get_private_key() -> str:
    """Return the private key from either the environment or a file.

    It is recommended to use the environment variable, but in case where the
    it cannot be used, the private key can be stored in a file. This could be
    the case when deploying to a platform which does not support multiline
    environment variables (e.g. Render).
    """
    private_key = os.getenv("GITHUB_PRIVATE_KEY")
    if private_key is None:
        private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
        if private_key_path is None:
            msg = (
                "Provide the private key using the GITHUB_PRIVATE_KEY environment "
                "variable or in a file using the GITHUB_PRIVATE_KEY_PATH environment "
                "variable. The path should either be absolute or relative to the "
                "repository root."
            )
            raise RuntimeError(msg)
        with open(private_key_path) as f:  # noqa: PTH123
            private_key = f.read()
    return private_key


class GitHubAPI(BaseGitHubAPI):
    def __init__(self, installation_id: int, *args: Any, **kwargs: Any) -> None:
        self._installation_id = installation_id
        super().__init__(*args, **kwargs)

    @property
    async def access_token(self) -> str:
        """Return the installation access token if it is present in the ``token_cache``
        else create a new token and store it for later use."""
        # Currently, the token lasts for 1 hour.
        # https://docs.github.com/en/developers/apps/differences-between-github-apps-and-oauth-apps#token-based-identification
        # We will store the token with key as installation ID so that the app can be
        # installed in multiple repositories (max installation determined by the
        # maxsize argument to the token_cache).
        if not hasattr(self, "_private_key"):
            self._private_key = _get_private_key()
        installation_id = self._installation_id
        if installation_id not in token_cache:
            data = await apps.get_installation_access_token(
                self,
                installation_id=str(installation_id),
                app_id=os.environ["GITHUB_APP_ID"],
                private_key=self._private_key,
            )
            token_cache[installation_id] = data["token"]
        return token_cache[installation_id]

    async def _request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes = b""
    ) -> tuple[int, Mapping[str, str], bytes]:
        """Make the API request and log the request-response cycle along with storing
        the response headers.

        This is the same method as ``gidgethub.aiohttp.GitHubAPI._request``.
        """
        async with self._session.request(
            method, url, headers=headers, data=body
        ) as response:
            self.log(response, body)
            return response.status, response.headers, await response.read()

    @staticmethod
    def log(response: ClientResponse, body: bytes) -> None:  # pragma: no cover
        """Log the request-response cycle for the GitHub API calls made by the bot.

        The logger information will be useful to know what actions the bot made.
        INFO: All actions taken by the bot.
        ERROR: Unknown error in the API call.
        """
        if response.status in STATUS_OK:
            loggerlevel = logger.info
            # Comments and reviews are too long to be logged for INFO level
            data = (
                response.url.name.upper()
                if response.url.name in ("comments", "reviews")
                else body.decode(UTF_8_CHARSET)
            )
        else:
            loggerlevel = logger.error
            data = body.decode(UTF_8_CHARSET)
        version = response.version
        if version is not None:
            version = f"{version.major}.{version.minor}"
        loggerlevel(
            'api "%s %s %s %s" => %s',
            response.method,
            response.url.raw_path_qs,
            f"{response.url.scheme.upper()}/{version}",
            data,
            f"{response.status}:{response.reason}",
        )
