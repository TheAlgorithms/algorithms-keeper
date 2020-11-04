import ast
from typing import List, Optional, Tuple, Union

from .constants import Label

SEP = "::"


class PullRequestFilesParser:
    """Parser for all the pull request Python files.

    This class should only be initialized once per pull request and then use
    its public method `parse_code` to parse and store all the necessary information.

    Methods:
        `parse_code(filename: str, code: bytes)`
            This is main function which will call all the other helper function,
            do the necessary checks and store the node paths for which the checks
            failed. All the failed node paths can be accessed using the attributes.

        `labels_to_add_and_remove(current_labels: List[str])`
            Returns a tuple of two list: first one will contain the labels to add
            and the second list will contain the labels to remove. The order do matter.

        `create_report_content()`
            Create the content of the pull request comment which will contain the
            information about what is missing to which functions/parameters.

    Attributes:
        `skip_doctest`: bool, indicating whether to skip doctest checking. This
                        property can be set as well.
    """

    def __init__(self) -> None:
        self._filename = ""
        self._skip_doctest = False
        self._require_doctest: List[str] = []
        self._require_return_annotation: List[str] = []
        self._require_annotations: List[str] = []
        self._require_descriptive_names: List[str] = []

    @property
    def skip_doctest(self) -> bool:
        """A property indicating whether to check for `doctest` or not. This property
        can be set after the class is initialized. Default value is `False`."""
        return self._skip_doctest

    @skip_doctest.setter
    def skip_doctest(self, value: bool) -> None:
        assert isinstance(value, bool), value
        self._skip_doctest = value

    def parse_code(self, filename: str, code: Union[bytes, str]) -> None:
        """Parse the Python code for doctest, type hints and descriptive names.

        This is the main function to be called with the filename and the source
        code in bytes or string format. This will call the other helper function
        which does the actual parsing and will mutate the property list with the
        node path for which the tests fail.
        """
        self._filename = filename
        tree = ast.parse(code).body
        for node in tree:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._parse_function(node)
            elif isinstance(node, ast.ClassDef):
                self._parse_class(node)

    def labels_to_add_and_remove(
        self,
        current_labels: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Return which labels to add and remove from the given pull request according
        to the current labels given.

        NOTE: This method should be called only after all the parsing is done otherwise
        it might return incomplete information.
        """
        labels_to_add = []
        labels_to_remove = []

        # Add or remove REQUIRE_TEST label
        if self._require_doctest:
            if Label.REQUIRE_TEST not in current_labels:
                labels_to_add.append(Label.REQUIRE_TEST)
        elif Label.REQUIRE_TEST in current_labels:
            labels_to_remove.append(Label.REQUIRE_TEST)

        # Add or remove DESCRIPTIVE_NAMES label
        if self._require_descriptive_names:
            if Label.DESCRIPTIVE_NAMES not in current_labels:
                labels_to_add.append(Label.DESCRIPTIVE_NAMES)
        elif Label.DESCRIPTIVE_NAMES in current_labels:
            labels_to_remove.append(Label.DESCRIPTIVE_NAMES)

        # Add or remove ANNOTATIONS label
        if self._require_annotations or self._require_return_annotation:
            if Label.ANNOTATIONS not in current_labels:
                labels_to_add.append(Label.ANNOTATIONS)
        elif Label.ANNOTATIONS in current_labels:
            labels_to_remove.append(Label.ANNOTATIONS)

        return labels_to_add, labels_to_remove

    def create_report_content(self) -> str:  # pragma: no cover
        """Create the report content for the current pull request as per the
        stored data in the parser.

        The report content will be in the following format:

        ---

        ### {Following functions/parameters require ...},
            where '...' can be tests, type hints, etc
        - [ ] Function or parameter node path where the requirement is missing
        ---

        NOTE: The report will only contain missing requirements.
        """
        content = []

        if self._require_doctest:
            content.append(
                "\n### Following functions require tests "
                "[`doctest`/`unittest`/`pytest`]:\n"
                "- [ ] {}\n".format("\n- [ ] ".join(self._require_doctest))
            )
        if self._require_descriptive_names:
            content.append(
                "\n### Following functions/parameters require descriptive names:\n"
                "- [ ] {}\n".format("\n- [ ] ".join(self._require_descriptive_names))
            )
        if self._require_return_annotation:
            content.append(
                "\n### Following functions require return type hints:\n"
                "***NOTE: If the function returns `None` then provide the type hint as "
                "`def function() -> None`***\n"
                "- [ ] {}\n".format("\n- [ ] ".join(self._require_return_annotation))
            )
        if self._require_annotations:
            content.append(
                "\n### Following function parameters require type hints:\n"
                "- [ ] {}\n".format("\n- [ ] ".join(self._require_annotations))
            )
        return "".join(content)

    def _parse_function(
        self,
        function: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        *,
        cls_name: Optional[str] = None,
    ) -> None:
        """Helper function for parsing the function node
        The order of checking is important:

        First check all the function related checks:
        - Function name is descriptive or not
        - `doctest` is present in the function docstring or not
        - Function has return annotation or not

        Then check all the argument related checks:
        - Argument name is descriptive or not
        - Argument has return annotation or not

        If the `cls_name` argument is not None, it means that the function is inside
        the class. This will make sure the node path is constructed appropriately.
        """
        func_name = function.name
        if len(func_name) == 1:
            self._require_descriptive_names.append(
                self._node_path(cls_name=cls_name, func_name=func_name)
            )
        if not self._skip_doctest and func_name != "__init__":
            docstring = ast.get_docstring(function)
            if docstring:
                for line in docstring.split("\n"):
                    line = line.strip()
                    if line.startswith(">>>"):
                        break
                else:
                    self._require_doctest.append(
                        self._node_path(cls_name=cls_name, func_name=func_name)
                    )
            # If `docstring` is absent from the function, we will count it as
            # `doctest` not present.
            else:
                self._require_doctest.append(
                    self._node_path(cls_name=cls_name, func_name=func_name)
                )
        if not function.returns:
            self._require_return_annotation.append(
                self._node_path(cls_name=cls_name, func_name=func_name)
            )
        for arg in function.args.args:
            arg_name = arg.arg
            # continue only if `self` is from a method
            if cls_name and arg_name == "self":
                continue
            if len(arg_name) == 1:
                self._require_descriptive_names.append(
                    self._node_path(
                        cls_name=cls_name, func_name=func_name, arg_name=arg_name
                    )
                )
            if not arg.annotation:
                self._require_annotations.append(
                    self._node_path(
                        cls_name=cls_name, func_name=func_name, arg_name=arg_name
                    )
                )

    def _parse_class(self, klass: ast.ClassDef) -> None:
        # A method is basically a function inside a class
        cls_name = klass.name
        if len(cls_name) == 1:
            self._require_descriptive_names.append(self._node_path(cls_name=cls_name))
        for cls_node in klass.body:
            if isinstance(cls_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._parse_function(cls_node, cls_name=cls_name)

    def _node_path(
        self,
        *,
        cls_name: Optional[str] = None,
        func_name: Optional[str] = None,
        arg_name: Optional[str] = None,
    ) -> str:
        path: List[str] = [self._filename]
        if cls_name:
            path.append(cls_name)
        if func_name:
            path.append(func_name)
        if arg_name:
            path.append(arg_name)
        return "`{}`".format(SEP.join(path))
