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
