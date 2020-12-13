from fixit import add_lint_rule_tests_to_module

from algorithms_keeper.parser.python_parser import RULES_DOTPATH, get_rules_from_config

add_lint_rule_tests_to_module(
    module_attrs=globals(), rules=get_rules_from_config(), rules_package=RULES_DOTPATH
)
