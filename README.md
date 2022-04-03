<div align="center">

# algorithms-keeper
[![CI](https://github.com/TheAlgorithms/algorithms-keeper/actions/workflows/main.yml/badge.svg)](https://github.com/TheAlgorithms/algorithms-keeper/actions/workflows/main.yml)
[![codecov](https://codecov.io/gh/TheAlgorithms/algorithms-keeper/branch/master/graph/badge.svg?token=QYAZ665UJL)](https://codecov.io/gh/TheAlgorithms/algorithms-keeper)
[![code style: black](https://img.shields.io/static/v1?label=code%20style&message=black&color=black)](https://github.com/psf/black)
[![Checked with mypy](https://img.shields.io/static/v1?label=mypy&message=checked&color=2a6db2&labelColor=505050)](http://mypy-lang.org/)

</div>

A bot for [TheAlgorithms/Python](https://www.github.com/TheAlgorithms/Python) repository. This bot is based on [this tutorial](https://github-app-tutorial.readthedocs.io/en/latest/index.html) and also inspired by the ones working for the [CPython](https://github.com/python/cpython) repository which are [miss-islington](https://github.com/python/miss-islington), [bedevere](https://github.com/python/bedevere) and [the-knights-who-say-ni](https://github.com/python/the-knights-who-say-ni). This bot is basically a GitHub app which can be installed in any repository using [this link](https://github.com/apps/algorithms-keeper).

***NOTE: This bot is highly configured for [TheAlgorithms/Python](https://www.github.com/TheAlgorithms/Python) repository. DO NOT INSTALL the bot without reading what it actually does.***

## What the bot does:

### Greet the user for installing the app
Open an issue with the message greeting the user who either installed the app or added a new repository to the installed app and then close the issue.

### Add or remove label(s) to pull requests
- To indicate that some tests are failing for this pull request if it is not present and remove it when all the tests are passing. It does nothing if the tests are already passing. ***NOTE: This check will be skipped if the pull request is in draft mode.***
- To indicate the stage the pull request is currently at. This is a cycle of two labels which indicates the two stages: The pull request requires a review/re-review, or a maintainer has requested changes for the pull request.
- To indicate whether the pull request contains merge conflicts or not.

The pull request stages can be best described in a [graphviz](http://www.webgraphviz.com/) diagram whose code is in the [pull requests module](https://github.com/TheAlgorithms/algorithms-keeper/blob/master/algorithms_keeper/event/pull_request.py#L3).

### Close invalid pull requests
A pull request is considered invalid if:
- It doesn't contain any description.
- The user has not ticked any of the checkboxes in the provided pull request template.
- The file extension is invalid. For now only PRs with extensionless files are closed.

***NOTE: These checks will be skipped for any member or owner of the organization and also for the pull request which is in draft mode.***

### Close additional pull requests by user
A user will be allowed a fix number of pull requests at a time which will be indicated by the `MAX_PR_BY_USER` constant. This is done to avoid spam pull requests. This can be disabled by updating the constant value to 0: `MAX_PR_BY_USER = 0`.

***NOTE: These checks will be skipped for any member or owner of the organization and also for the pull request which is in draft mode.***

### Check all Python files in a pull request
All the Python files will be checked for tests [`doctest`/`unittest`/`pytest`], type hints and descriptive class/function/parameter names. Labels will be added and/or removed according to the latest commit in a pull request. The bot will post the review with all the details regarding the missing requirements.

***NOTE: These checks will be skipped if the pull request is in draft mode and if the pull request is invalid.***

### Commands
Some actions of the bot can be triggered using commands:
- `@algorithms-keeper review` to trigger the checks for only added pull request files.
- `@algorithms-keeper review-all` to trigger the checks for all the pull request files, including the modified files. As we cannot post review comments on lines not part of the diff, this command only modify the labels accordingly.

***NOTE: Commands are in BETA and valid only if it is commented on a pull request and only by either a member or owner of the organization.***

## Logging
Logging is done using the standard library logging module. All the API calls made by the bot are being logged at INFO level and `aiohttp.log.access_logger` is logging the POST requests made by GitHub for delivering the payload. Other minor events relevant to the repository is also being logged along with using the using [Sentry](https://sentry.io/). The logs can be viewed best using the following command ([_requires Heroku CLI_](https://devcenter.heroku.com/articles/heroku-cli#download-and-install)):
```shell
heroku logs -a algorithms-keeper -t
```
