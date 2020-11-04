from typing import Any, Dict, List, Optional

from gidgethub import sansio

MOCK_TOKEN = 19
MOCK_INSTALLATION_ID = 1234


async def mock_return(*args, **kwargs) -> Dict[str, Any]:
    return {"token": MOCK_TOKEN}


class MockGitHubAPI:
    def __init__(
        self,
        *,
        getitem: Optional[Dict[str, Any]] = None,
        getiter: Optional[Dict[str, Any]] = None,
        post: Optional[Dict[str, Any]] = None,
        patch: Optional[Dict[str, Any]] = None,
        put: Optional[Dict[str, Any]] = None,
        delete: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._getitem_return = getitem
        self._getiter_return = getiter
        self._post_return = post
        self._patch_return = patch
        self._put_return = put
        self._delete_return = delete
        self.getitem_url: List[str] = []
        self.getiter_url: List[str] = []
        self.post_url: List[str] = []
        self.post_data: List[str] = []
        self.patch_url: List[str] = []
        self.patch_data: List[str] = []
        self.delete_url: List[str] = []
        self.delete_data: List[str] = []

    async def getitem(self, url, *, accept=sansio.accept_format(), oauth_token=None):
        self.getitem_url.append(url)
        return self._getitem_return[url]

    async def getiter(self, url, *, accept=sansio.accept_format(), oauth_token=None):
        self.getiter_url.append(url)
        data = self._getiter_return[url]
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        for item in data:
            yield item

    async def post(self, url, *, data, accept=sansio.accept_format(), oauth_token=None):
        self.post_url.append(url)
        self.post_data.append(data)
        return self._post_return[url]

    async def patch(
        self, url, *, data, accept=sansio.accept_format(), oauth_token=None
    ):
        self.patch_url.append(url)
        self.patch_data.append(data)
        return self._patch_return[url]

    async def delete(
        self, url, *, data={}, accept=sansio.accept_format(), oauth_token=None
    ):
        self.delete_url.append(url)
        self.delete_data.append(data)
        return self._delete_return[url]
