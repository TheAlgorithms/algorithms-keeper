from typing import Any, Dict, List, Optional, cast

from gidgethub import aiohttp, sansio

# Meta information
token = "12345"
number = 1
repository = "user/testing"
sha = "a06212024d8f1c339c55c5ea4568ech155368c21"
user = "user"
comment = "This is a comment"

# Issue
html_issue_url = f"https://github.com/{repository}/issues/{number}"
issue_path = f"/repos/{repository}/issues"
issue_url = f"https://api.github.com/repos/{repository}/issues/{number}"
labels_url = f"{issue_url}/labels"
comments_url = f"{issue_url}/comments"
comment_url = f"{comments_url}/{number}"
reactions_url = f"{comment_url}/reactions"

# Pull request
pr_url = f"https://api.github.com/repos/{repository}/pulls/{number}"
html_pr_url = f"https://github.com/{repository}/pulls/{number}"
reviewers_url = f"{pr_url}/requested_reviewers"
files_url = f"{pr_url}/files"
contents_url1 = f"https://api.github.com/repos/{repository}/contents/test1.py?ref={sha}"
contents_url2 = f"https://api.github.com/repos/{repository}/contents/test2.py?ref={sha}"
review_url = f"{pr_url}/reviews"

# Check run
check_run_url = f"/repos/{repository}/commits/{sha}/check-runs"

# Search
search_url = (
    f"/search/issues?q=type:pr+state:open+draft:false+repo:{repository}+sha:{sha}"
)
pr_user_search_url = (
    f"/search/issues?q=type:pr+state:open+repo:{repository}+author:{user}"
)

# PR template ticked
CHECKBOX_TICKED = (
    "### **Describe your change:**\r\n\r\n\r\n\r\n* [ ] Add an algorithm?\r\n* [x]"
    " Fix a bug or typo in an existing algorithm?\r\n* [x] Documentation change?"
    "\r\n\r\n### **Checklist:**\r\n* [x] I have read [CONTRIBUTING.md]"
    "(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md).\r\n* "
    "[x] This pull request is all my own work -- I have not plagiarized.\r\n* [x] "
    "I know that pull requests will not be merged if they fail the automated tests."
    "\r\n* [x] This PR only changes one algorithm file.  To ease review, please open "
    "separate PRs for separate algorithms.\r\n* [x] All new Python files are placed "
    "inside an existing directory.\r\n* [x] All filenames are in all lowercase "
    "characters with no spaces or dashes.\r\n* [x] All functions and variable names "
    "follow Python naming conventions.\r\n* [x] All function parameters and return "
    "values are annotated with Python [type hints]"
    "(https://docs.python.org/3/library/typing.html).\r\n* [x] All functions have "
    "[doctests](https://docs.python.org/3/library/doctest.html) that pass the "
    "automated testing.\r\n* [x] All new algorithms have a URL in its comments that "
    "points to Wikipedia or other similar explanation.\r\n* [ ] If this pull request "
    "resolves one or more open issues then the commit message contains "
    "`Fixes: #{$ISSUE_NO}`.\r\n"
)

# PR template ticked with uppercase 'X'
CHECKBOX_TICKED_UPPER = (
    "### **Describe your change:**\r\n\r\n\r\n\r\n* [ ] Add an algorithm?\r\n* [X]"
    " Fix a bug or typo in an existing algorithm?\r\n* [X] Documentation change?"
    "\r\n\r\n### **Checklist:**\r\n* [X] I have read [CONTRIBUTING.md]"
    "(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md).\r\n* "
    "[X] This pull request is all my own work -- I have not plagiarized.\r\n* [X] "
    "I know that pull requests will not be merged if they fail the automated tests."
    "\r\n* [X] This PR only changes one algorithm file.  To ease review, please open "
    "separate PRs for separate algorithms.\r\n* [X] All new Python files are placed "
    "inside an existing directory.\r\n* [X] All filenames are in all lowercase "
    "characters with no spaces or dashes.\r\n* [X] All functions and variable names "
    "follow Python naming conventions.\r\n* [X] All function parameters and return "
    "values are annotated with Python [type hints]"
    "(https://docs.python.org/3/library/typing.html).\r\n* [X] All functions have "
    "[doctests](https://docs.python.org/3/library/doctest.html) that pass the "
    "automated testing.\r\n* [X] All new algorithms have a URL in its comments that "
    "points to Wikipedia or other similar explanation.\r\n* [ ] If this pull request "
    "resolves one or more open issues then the commit message contains "
    "`Fixes: #{$ISSUE_NO}`.\r\n"
)

# PR template not ticked
CHECKBOX_NOT_TICKED = (
    "### **Describe your change:**\r\n\r\n\r\n\r\n* [ ] Add an algorithm?\r\n* [ ]"
    " Fix a bug or typo in an existing algorithm?\r\n* [ ] Documentation change?"
    "\r\n\r\n### **Checklist:**\r\n* [ ] I have read [CONTRIBUTING.md]"
    "(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md).\r\n* "
    "[ ] This pull request is all my own work -- I have not plagiarized.\r\n* [ ] "
    "I know that pull requests will not be merged if they fail the automated tests."
    "\r\n* [ ] This PR only changes one algorithm file.  To ease review, please open "
    "separate PRs for separate algorithms.\r\n* [ ] All new Python files are placed "
    "inside an existing directory.\r\n* [ ] All filenames are in all lowercase "
    "characters with no spaces or dashes.\r\n* [ ] All functions and variable names "
    "follow Python naming conventions.\r\n* [ ] All function parameters and return "
    "values are annotated with Python [type hints]"
    "(https://docs.python.org/3/library/typing.html).\r\n* [ ] All functions have "
    "[doctests](https://docs.python.org/3/library/doctest.html) that pass the "
    "automated testing.\r\n* [ ] All new algorithms have a URL in its comments that "
    "points to Wikipedia or other similar explanation.\r\n* [ ] If this pull request "
    "resolves one or more open issues then the commit message contains "
    "`Fixes: #{$ISSUE_NO}`.\r\n"
)


async def mock_return(*args, **kwargs) -> Dict[str, Any]:
    return {"token": token}


class _MockGitHubAPI:
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

    @property
    async def access_token(self) -> str:
        return token

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
        self, url, *, data=None, accept=sansio.accept_format(), oauth_token=None
    ):
        self.delete_url.append(url)
        if data is not None:
            self.delete_data.append(data)
        return self._delete_return[url]


MockGitHubAPI = cast(aiohttp.GitHubAPI, _MockGitHubAPI)
