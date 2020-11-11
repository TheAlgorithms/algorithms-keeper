# algorithms-keeper
[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/dhruvmanila/algorithms-keeper/CI?label=CI&logo=github&style=flat-square)](https://github.com/dhruvmanila/algorithms-keeper/actions)
[![Codecov](https://img.shields.io/codecov/c/gh/dhruvmanila/algorithms-keeper?logo=codecov&style=flat-square)](https://codecov.io/gh/dhruvmanila/algorithms-keeper)
[![code style: black](https://img.shields.io/static/v1?label=code%20style&message=black&color=black&style=flat-square)](https://github.com/psf/black)

A bot for [TheAlgorithms/Python](https://www.github.com/TheAlgorithms/Python) repository. This bot is based on [this tutorial](https://github-app-tutorial.readthedocs.io/en/latest/index.html) and also inspired by the ones working for the [CPython](https://github.com/python/cpython) repository which are [miss-islington](https://github.com/python/miss-islington), [bedevere](https://github.com/python/bedevere) and [the-knights-who-say-ni](https://github.com/python/the-knights-who-say-ni). This bot is basically a GitHub app which can be installed in any repository using [this link](https://github.com/apps/algorithms-keeper).

***NOTE: This bot is highly configured for [TheAlgorithms/Python](https://www.github.com/TheAlgorithms/Python) repository. DO NOT INSTALL the bot without reading what it actually does.***

## Greet the user for installing the app
Open an issue with the message greeting the user who either installed the app or added a new repository to the installed app and then close the issue.

## Add and remove label to PRs when any test fails
Add a label to indicate that the tests are failing for this PR if it is not present and removes it when the tests pass. It does nothing if the tests are already passing.

## Close invalid PRs with comment and an optional label
A pull request is considered invalid if:
- It doesn't contain any description.
- The user has not ticked any of the checkboxes in the provided pull request template.
- The file extension is invalid. For now only PRs with extensionless files are closed.

***NOTE: These checks will be skipped for any member or owner of the organization.***

## Close additional PRs by user with a comment
A user will be allowed a fix number of pull requests at a time which will be indicated by the `MAX_PR_BY_USER` constant. This is done so as to avoid spam PRs.

***NOTE: These checks will be skipped for any member or owner of the organization.***

## Check all Python files in a PR
All the Python files will be checked for tests [`doctest`/`unittest`/`pytest`], type hints and descriptive class/function/parameter names. Labels will be added and/or removed according to the latest commit in a PR. A report will be created and commented by the bot if there are any errors found, but ***only*** when a PR is ***opened*** and not on the subsequent commits.

---
###### TODO: https://github.com/dhruvmanila/algobot/blob/master/.github/TODO.md
