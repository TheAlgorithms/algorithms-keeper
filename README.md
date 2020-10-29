# algorithms-bot
[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/dhruvmanila/algobot/CI?label=CI&logo=github&style=flat-square)](https://github.com/dhruvmanila/algobot/actions)
[![Codecov](https://img.shields.io/codecov/c/gh/dhruvmanila/algobot?logo=codecov&style=flat-square)](https://codecov.io/gh/dhruvmanila/algobot)
[![code style: black](https://img.shields.io/static/v1?label=code%20style&message=black&color=black&style=flat-square)](https://github.com/psf/black)

A bot for [TheAlgorithms/Python](https://www.github.com/TheAlgorithms/Python) repository. This bot is highly inspired by the ones working for CPython repository which are [miss-islington](https://github.com/python/miss-islington), [bedevere](https://github.com/python/bedevere) and [the-knights-who-say-ni](https://github.com/python/the-knights-who-say-ni)

## Add and remove label to PRs when any test fails
Add a label to indicate that the tests are failing for this PR if it is not present and removes it when the tests pass. It does nothing if the tests are already passing.

---
### TODO: 
- [ ] Add a comment indicating the user for where to look in case of failed tests
- [ ] Auto close a pull request which do not contain any tests (`doctest`/`unittest`/`pytest`)
- [ ] Auto close a pull request which do not contain any type hints (use `ast` or `inspect`?)
- [ ] Auto close a pull request by a user who already has an open pull request (maybe allow 2 open pull requests at a time?)

