from typing import Mapping, Tuple

from gidgethub.abc import UTF_8_CHARSET
from gidgethub.aiohttp import GitHubAPI as BaseGitHubAPI

from .log import STATUS_OK, inject_status_color, logger

TOKEN_ENDPOINT = "access_tokens"


class GitHubAPI(BaseGitHubAPI):  # pragma: no cover

    LOG_FORMAT = 'api "%(method)s %(path)s %(data)s %(version)s" => %(status)s'

    async def _request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes = b""
    ) -> Tuple[int, Mapping[str, str], bytes]:
        """This is the same method as `gidgethub.aiohttp.GitHubAPI._request` with the
        addition of logging the request-response cycle. No need to cover this function.

        The logger information will be useful to know what actions the bot made.
        INFO: All actions taken by the bot.
        ERROR: Unknown error in the API call.
        """
        async with self._session.request(
            method, url, headers=headers, data=body
        ) as response:
            # We don't want to reveal the `installation_id` from the URL.
            if response.url.name != TOKEN_ENDPOINT:
                inject_status_color(response.status)
                data = "NONE" if body == b"" else body.decode(UTF_8_CHARSET)
                # Comments are too long to be logged.
                if response.url.name == "comments":
                    data = "COMMENT"
                loggerlevel = (
                    logger.info if response.status in STATUS_OK else logger.error
                )
                loggerlevel(
                    self.LOG_FORMAT,
                    {
                        "method": method,
                        # host is always going to be 'api.github.com'.
                        "path": response.url.raw_path_qs,
                        "version": f"{response.url.scheme.upper()}/"
                        f"{response.version.major}.{response.version.minor}",
                        "data": data,
                        "status": f"{response.status}:{response.reason}",
                    },
                )
            return response.status, response.headers, await response.read()
