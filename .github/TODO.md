# TODO: 

### Event: `check_run`
- [ ] Add a comment indicating the user for where to look in case of failed tests

### Event: `pull_request`
- [ ] Check whether the description is empty or not, if it is then close the PR.
- [ ] Check for type hints and tests in the submitted files and label it appropriately (close it when there are more number of open PRs)
- [ ] Check whether the user has an open PR and if so then make an appropriate comment and close the PR. `MAX_PR_PER_USER=?` (maybe allow 2 open pull requests at a time?)
- [ ] Check for file extension and close the PR where the file extension (is | is not) included in the list. `.github/` directory should be ignored. `ACCEPTED_FILE_EXTENSION` or `EXCLUDED_FILE_EXTENSION`
- [ ] Check if the default pull request message has check box ticked or not. If not then close the PR with an appropriate message.