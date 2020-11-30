"""Package level constants

Only the constants which are accessed throughout the module are defined here.
Constants related to a specific event are defined in their own module. So a
constant related to pull request will be defined in the `pull_requests` module.
"""


class Label:
    FAILED_TEST = "Status: Tests are failing"
    AWAITING_REVIEW = "Status: awaiting reviews"
    ANNOTATIONS = "Require: Type hints"
    REQUIRE_TEST = "Require: Tests"
    DESCRIPTIVE_NAMES = "Require: Descriptive names"
    CHANGES_REQUESTED = "Status: awaiting changes"
    INVALID = "invalid"
    DOCUMENTATION = "Type: documentation"
    ENHANCEMENT = "Type: enhancement"


# If these labels are on a pull request, then the pull request is not ready to be
# reviewed by a maintainer and thus, remove Label.AWAITING_REVIEW if present.
PR_NOT_READY_LABELS = (
    Label.FAILED_TEST,
    Label.REQUIRE_TEST,
    Label.DESCRIPTIVE_NAMES,
    Label.ANNOTATIONS,
    Label.INVALID,
)


# All the comments made by the bot

GREETING_COMMENT = """\
This is the algorithms-keeper at your service! Thank you for installing me @{login}.
"""

MAX_PR_REACHED_COMMENT = """\
# Multiple Pull Request Detected

@{user_login}, we are extremely excited that you want to submit multiple algorithms \
in this repository but we have a limit on how many pull request a user can keep open \
at a time. This is to make sure all maintainers and users focus on a limited number of \
pull requests at a time to maintain the quality of the code.

This pull request is being closed as the user already has an open pull request. \
Please focus on your previous pull request before opening another one. Thank you for \
your cooperation.

User opened pull requests (including this one): {pr_number}
"""

EMPTY_ISSUE_BODY_COMMENT = """\
# Closing this issue as invalid

@{user_login}, this issue is being closed because the description is empty. \
If you believe that this is being done by mistake, please open the issue with the \
necessary details regarding the problem.
"""

EMPTY_BODY_COMMENT = """\
# Closing this pull request as invalid

@{user_login}, this pull request is being closed because the description is empty. \
If you believe that this is being done by mistake, please read our \
[Contributing guidelines]\
(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md) before opening \
a new pull request with our [template]\
(https://github.com/TheAlgorithms/Python/blob/master/.github/pull_request_template.md) \
properly filled out. Thank you for your interest in our project.
"""

CHECKBOX_NOT_TICKED_COMMENT = """\
# Closing this pull request as invalid

@{user_login}, this pull request is being closed as none of the checkboxes have been \
marked. It is important that you go through the checklist and mark the ones relevant \
to this pull request. Please read the [Contributing guidelines]\
(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md).

If you're facing any problem on how to mark a checkbox, please read the following \
instructions:
- Read a point one at a time and think if it is relevant to the pull request or not.
- If it is, then mark it by putting a `x` between the square bracket like so: `[x]`

***NOTE: Only `[x]` is supported so if you have put any other letter or symbol \
between the brackets, that will be marked as invalid. If that is the case then please \
open a new pull request with the appropriate changes.***
"""

NO_EXTENSION_COMMENT = """\
# Closing this pull request as invalid

@{user_login}, this pull request is being closed as the files submitted contains no \
extension. This repository only accepts Python algorithms. Please read the \
[Contributing guidelines]\
(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md) first.
"""

PR_REPORT_COMMENT = """\
# Pull Request Report

@{user_login} Hello! I'm a bot made to check all the pull request Python files. \
First of all, I want to say thank you for your time and interest in this project and \
for opening a pull request. There seems to be missing requirements in some of the \
Python files submitted in this pull request. Please read through the report and make \
the necessary changes. You can take a look at the relevant links provided after the \
report.

<details><summary><b>What are node paths? 🔽</b></summary>

> The report contains headings and a checklist where the items are paths to the \
class/function/parameter where the requirement is missing. Node paths are double \
colon `::` separated names and can be in any of the following format:
> - Class path: `[file_name]::[class_name]`
> - Function path: `[file_name]::[function_name]`
> - Function parameter path: `[file_name]::[function_name]::[parameter_name]`
> - Method path: `[file_name]::[class_name]::[function_name]`
> - Method parameter path: \
`[file_name]::[class_name]::[function_name]::[parameter_name]`

</details>
{content}

<details><summary><b>Relevant links 🔽</b></summary>

> - [Contributing guidelines]\
(https://github.com/TheAlgorithms/Python/blob/master/CONTRIBUTING.md)
> - [Project Euler solution guidelines]\
(https://github.com/TheAlgorithms/Python/blob/master/project_euler/README.md)
> - [Type hints](https://docs.python.org/3/library/typing.html)
> - [`doctest`](https://docs.python.org/3/library/doctest.html)
> - [`unittest`](https://docs.python.org/3/library/unittest.html)
> - [`pytest`](https://docs.pytest.org/en/stable/)

</details>
"""
