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


# If these labels are on a pull request, then the pull request is not ready to be
# reviewed by a maintainer and thus, remove Label.AWAITING_REVIEW if present.
PR_NOT_READY_LABELS = (
    Label.FAILED_TEST,
    Label.REQUIRE_TEST,
    Label.DESCRIPTIVE_NAMES,
    Label.ANNOTATIONS,
    Label.INVALID,
)
