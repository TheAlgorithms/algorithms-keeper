from fixit import LintRule
from libcst import CSTNode


class ReviewLintRule(LintRule):
    """Review every violation, including code with lint suppression comments."""

    def ignore_lint(self, node: CSTNode) -> bool:
        # Preserve the bot's use_ignore_comments=False policy from Fixit 0.1.
        return False
