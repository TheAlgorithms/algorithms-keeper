import ast
import functools
from typing import List, Optional, Union


class CodeParser:
    """Python code parser for all the pull request files.

    This class should only be initialized once per pull request and then use
    its public method `parse_code` to parse and store all the necessary node
    paths. Node path will be of the following format:

    `{filepath}::{class_name}::{function_name}::{parameter_name}`

    Class name will be added to the path only if the function node is a method.

    Methods:
        `parse_code(filename: str, code: bytes)`
            This is main function which will call all the other helper function,
            do the necessary checks and store the node paths for which the checks
            failed. All the failed node paths can be accessed using the attributes.

    Attributes (Read only):
        `require_doctest`: Function node paths which do not contain `doctest`
        `require_return_annotation`: Function node paths which do not contain return
                                     annotation
        `require_annotations`: Parameter node paths which do not contain annotation
        `require_descriptive_names`: Parameter/Function node paths whose name is
                                     of length 1

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

    # Caching all the list properties.
    # NOTE: Do not call the property in any of the methods. Only call it after
    # all the files are parsed.
    @functools.cached_property
    def require_doctest(self) -> List[str]:
        """Function node path that requires `doctest`. If the function is inside
        a class, it will include the class name in the path.

        Format:
        `{filepath}::{function_name}`
        or
        `{filepath}::{class_name}::{function_name}`
        """
        return self._require_doctest.copy()

    @functools.cached_property
    def require_return_annotation(self) -> List[str]:
        """Function node path that requires return annotation. If the function is
        inside a class, it will include the class name in the path.

        Format:
        `{filepath}::{function_name}`
        or
        `{filepath}::{class_name}::{function_name}`
        """
        return self._require_return_annotation.copy()

    @functools.cached_property
    def require_annotations(self) -> List[str]:
        """Parameter node path that requires annotation. If the function is inside
        a class, it will include the class name in the path.

        Format:
        `{filepath}::{function_name}::{param_name}`
        or
        `{filepath}::{class_name}::{function_name}::{param_name}`
        """
        return self._require_annotations.copy()

    @functools.cached_property
    def require_descriptive_names(self) -> List[str]:
        """Parameter/Function node path that requires descriptive names. If the
        function is inside a class, it will include the class name in the path.

        Format:
        `{filepath}::{function_name}`
        `{filepath}::{function_name}::{param_name}`
        or
        `{filepath}::{class_name}::{function_name}`
        `{filepath}::{class_name}::{function_name}::{param_name}`
        """
        return self._require_descriptive_names.copy()

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
                self._node_path(func_name=func_name, cls_name=cls_name)
            )
        if not self._skip_doctest:
            docstring = ast.get_docstring(function)
            if docstring:
                for line in docstring.split("\n"):
                    line = line.strip()
                    if line.startswith(">>>"):
                        break
                else:
                    self._require_doctest.append(
                        self._node_path(func_name=func_name, cls_name=cls_name)
                    )
            # If `docstring` is absent from the function, we will count it as
            # `doctest` not present.
            else:
                self._require_doctest.append(
                    self._node_path(func_name=func_name, cls_name=cls_name)
                )
        if not function.returns:
            self._require_return_annotation.append(
                self._node_path(func_name=func_name, cls_name=cls_name)
            )
        for arg in function.args.args:
            arg_name = arg.arg
            if arg_name == "self":
                continue
            if len(arg_name) == 1:
                self._require_descriptive_names.append(
                    self._node_path(
                        func_name=func_name, cls_name=cls_name, arg_name=arg_name
                    )
                )
            if not arg.annotation:
                self._require_annotations.append(
                    self._node_path(
                        func_name=func_name, cls_name=cls_name, arg_name=arg_name
                    )
                )

    def _parse_class(self, klass: ast.ClassDef) -> None:
        # A method is basically a function inside a class
        cls_name = klass.name
        for cls_node in klass.body:
            if isinstance(cls_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._parse_function(cls_node, cls_name=cls_name)

    def _node_path(
        self,
        *,
        func_name: str,
        cls_name: Optional[str] = None,
        arg_name: Optional[str] = None,
    ) -> str:
        path: List[str] = [self._filename, func_name]
        if cls_name:
            path.insert(1, cls_name)
        if arg_name:
            path.append(arg_name)
        return "`{}`".format("::".join(path))
