from gidgethub import sansio

MOCK_TOKEN = 19
MOCK_INSTALLATION_ID = 1234


async def mock_return(*args, **kwargs):
    return {"token": MOCK_TOKEN}


class MockGitHubAPI:
    def __init__(
        self,
        *,
        getitem=None,
        getiter=None,
        post=None,
        patch=None,
        put=None,
        delete=None
    ) -> None:
        self._getitem_return = getitem
        self._getiter_return = getiter
        self._post_return = post
        self._patch_return = patch
        self._put_return = put
        self._delete_return = delete
        self.getitem_url = None
        self.getiter_url = None
        self.post_url = self.post_data = None
        self.patch_url = self.patch_data = None
        self.put_url = self.put_data = None
        self.delete_url = None

    async def getitem(self, url, *, accept=sansio.accept_format(), oauth_token=None):
        self.getitem_url = url
        return self._getitem_return[url]

    async def getiter(self, url, *, accept=sansio.accept_format(), oauth_token=None):
        self.getiter_url = url
        for item in self._getiter_return[url]:
            yield item

    async def post(self, url, *, data, accept=sansio.accept_format(), oauth_token=None):
        self.post_url = url
        self.post_data = data
        return self._post_return

    async def patch(
        self, url, *, data, accept=sansio.accept_format(), oauth_token=None
    ):
        self.patch_url = url
        self.patch_data = data
        return self._patch_return

    async def put(
        self, url, *, data=b"", accept=sansio.accept_format(), oauth_token=None
    ):
        self.put_url = url
        self.put_data = data
        return self._put_return

    async def delete(
        self, url, *, data=b"", accept=sansio.accept_format(), oauth_token=None
    ):
        self.delete_url = url
        return self._delete_return
