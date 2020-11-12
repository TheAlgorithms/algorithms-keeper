# TODO

### Event: `check_run`
- [ ] Add a comment indicating the user for where to look in case of failed tests. Should we add the comment everytime the tests are failing or only on the first time?

### Event: `pull_request`
- [x] ~Check whether the description is empty or not, if it is then close the PR.~
- [x] ~Check for type hints and tests in the submitted files and label it appropriately (send a report when the PR is opened)~
- [x] ~Check whether the user has an open PR and if so then make an appropriate comment and close the PR. `MAX_PR_PER_USER=1`~
- [x] ~Check for file extension and close the PR if a file has no extension. `.github/` directory should be ignored.~
- [x] ~Check if the default pull request message has check box ticked or not. If not then close the PR with an appropriate message.~
- [x] ~Do not perform any checks if the PR is in `draft` mode.~
- [x] ~Perform all the checks when PR is `ready_for_review`~
- [x] ~Add `Status: awaiting changes` label when a review has been submitted. Remove it if the PR is approved.~

### Event: `issue`
- [x] ~Check whether the description is empty or not, if it is then close the issue.~