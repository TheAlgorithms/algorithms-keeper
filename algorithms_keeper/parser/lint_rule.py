from __future__ import annotations

from typing import TYPE_CHECKING

from fixit import LintRule

if TYPE_CHECKING:
    from libcst import CSTNode


class ReviewLintRule(LintRule):
    """Review every violation, including code with lint suppression comments."""

    def ignore_lint(self, node: CSTNode) -> bool:
        # Preserve the bot's use_ignore_comments=False policy from Fixit 0.1.
        return False
