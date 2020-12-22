import libcst as cst
import libcst.matchers as m
from fixit import CstContext, CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

INVALID_CAMEL_CASE_NAME: str = (
    "Class names should follow the [`CamelCase`]"
    + "(https://en.wikipedia.org/wiki/Camel_case) naming convention. "
    + "Please update the name of the class `{nodename}` accordingly. "
)

INVALID_SNAKE_CASE_NAME: str = (
    "Variable and function names should follow the [`snake_case`]"
    + "(https://en.wikipedia.org/wiki/Snake_case) naming convention. "
    + "Please update the name of the {nodetype} `{nodename}` accordingly. "
)


def _any_uppercase_letter(name: str) -> bool:
    """Check whether the given *name* contains any uppercase letter in it."""
    upper_count: int = len([letter for letter in name if letter.isupper()])
    # If the count value equals the length of name, the name is a CONSTANT.
    if upper_count and upper_count != len(name):
        return True
    return False


class NamingConventionRule(CstLintRule):

    VALID = [
        Valid("type_hint: str"),
        Valid("type_hint_var: int = 5"),
        Valid("CONSTANT = 10"),
        Valid("hello = 'world'"),
        Valid("snake_case = 'assign'"),
        Valid("for iteration in range(5): pass"),
        Valid("class _PrivateClass: pass"),
        Valid("class SomeClass: pass"),
        Valid("class One: pass"),
        Valid("def oneword(): pass"),
        Valid("def some_extra_words(): pass"),
        Valid("all = names_are = valid_in_multiple_assign = 5"),
        Valid("(walrus := 'operator')"),
        Valid("multiple, valid, assignments = 1, 2, 3"),
        Valid(
            """
            class Spam:
                def __init__(self, valid, another_valid):
                    self.valid = valid
                    self.another_valid = another_valid
                    self._private = None
                    self.__extreme_private = None

                def bar(self):
                    # This is just to test that the access is not being tested.
                    return self.some_Invalid_NaMe
            """
        ),
    ]

    INVALID = [
        Invalid("type_Hint_Var: int = 5"),
        Invalid("hellO = 'world'"),
        Invalid("ranDom_UpPercAse = 'testing'"),
        Invalid("for RandomCaps in range(5): pass"),
        Invalid("class _Invalid_PrivateClass: pass"),
        Invalid("class _invalidPrivateClass: pass"),
        Invalid("class lowerPascalCase: pass"),
        Invalid("class all_lower_case: pass"),
        Invalid("def oneWordInvalid(): pass"),
        Invalid("def Pascal_Case(): pass"),
        Invalid("valid = another_valid = Invalid = 5"),
        Invalid("(waLRus := 'operator')"),
        Invalid("def func(invalidParam, valid_param): pass"),
        Invalid("multiple, inValid, assignments = 1, 2, 3"),
        Invalid("[inside, list, inValid] = Invalid, 2, 3"),
        Invalid(
            """
            class Spam:
                def __init__(self, foo, bar):
                    self.foo = foo
                    self._Bar = bar
            """
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self._assigntarget_counter: int = 0

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        nodename = node.name.value
        for index, letter in enumerate(nodename):
            if letter == "_":
                continue
            # First non-underscore letter
            elif letter.islower() or "_" in nodename[index:]:
                self.report(node, INVALID_CAMEL_CASE_NAME.format(nodename=nodename))
            break

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        # The assignment target is optional, as it is possible to annotate an
        # expression without assigning to it: ``var: int``
        if node.value is not None:
            self._validate_snake_case_name(node, "variable")

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        self._assigntarget_counter += 1
        self._validate_snake_case_name(node, "variable")

    def leave_AssignTarget(self, node: cst.AssignTarget) -> None:
        self._assigntarget_counter -= 1

    def visit_Attribute(self, node: cst.Attribute) -> None:
        # We only care about assignment attribute for *self*.
        if self._assigntarget_counter > 0:
            self._validate_snake_case_name(node, "attribute")

    def visit_Element(self, node: cst.Element) -> None:
        # We only care about elements in *List* or *Tuple* for multiple assignments.
        if self._assigntarget_counter > 0:
            self._validate_snake_case_name(node, "variable")

    def visit_For(self, node: cst.For) -> None:
        self._validate_snake_case_name(node, "variable")

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._validate_snake_case_name(node, "function")

    def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
        self._validate_snake_case_name(node, "variable")

    def visit_Param(self, node: cst.Param) -> None:
        self._validate_snake_case_name(node, "parameter")

    def _validate_snake_case_name(self, node: cst.CSTNode, nodetype: str) -> None:
        """Validate that the provided node conforms to the *snake_case* naming
        convention. The validation will be done for the following nodes:

        - ``cst.AnnAssign`` (Annotated assignment), which means an assignment which is
          type annotated like so ``var: int = 5``, to check the name of the variable.
        - ``cst.AssignTarget``, the target for the assignment, which is the left side
          part of the assignment expression. This can be a simple *Name* node or a
          sequence type node like *List* or *Tuple* in case of multiple assignments.
        - ``cst.Attribute``, to test the variable names assigned to the instance. This
          will check only for the *self* attribute.
        - ``cst.Element``, this will only be checked if the elements come from multiple
          assignment targets which occurs only in case of *List* or *Tuple*.
        - ``cst.For``, to check the target name of the iterator in the for statement.
        - ``cst.FunctionDef`` to check the name of the function.
        - ``cst.NamedExpr`` to check the assigned name in the expression. Also known
          as the walrus operator, this expression allows you to make an assignment
          inside an expression like so ``var := 10``.
        - ``cst.Param`` to check the name of the function parameters.
        """
        namekey: str = "nodename"
        # The match and extraction code below is similar to three ``if`` statements to
        # ``isinstance`` calls and further either using ``m.extract`` or another
        # ``isinstance`` call to verify we have the ``cst.Name`` node, verifying whether
        # it conforms to the convention and extracting the name value.
        extracted = (
            m.extract(
                node,
                m.Element(
                    value=m.Name(
                        value=m.SaveMatchedNode(
                            m.MatchIfTrue(_any_uppercase_letter), namekey
                        )
                    )
                ),
            )
            or m.extract(
                node,
                m.Attribute(
                    value=m.Name(value="self"),
                    attr=m.Name(
                        value=m.SaveMatchedNode(
                            m.MatchIfTrue(_any_uppercase_letter), namekey
                        )
                    ),
                ),
            )
            or m.extract(
                node,
                m.TypeOf(m.FunctionDef, m.Param)(
                    name=m.Name(
                        value=m.SaveMatchedNode(
                            m.MatchIfTrue(_any_uppercase_letter), namekey
                        )
                    )
                ),
            )
            or m.extract(
                node,
                m.TypeOf(m.AnnAssign, m.AssignTarget, m.For, m.NamedExpr)(
                    target=m.Name(
                        value=m.SaveMatchedNode(
                            m.MatchIfTrue(_any_uppercase_letter), namekey
                        )
                    )
                ),
            )
        )

        if extracted is not None:
            self.report(
                node,
                INVALID_SNAKE_CASE_NAME.format(
                    nodetype=nodetype, nodename=extracted[namekey]
                ),
            )
