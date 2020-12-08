def no_doctest() -> None:
    """
    This function contains docstring but no doctest
    """
    return None


# This function do not contain docstring and doctest
def no_docstring_and_doctest() -> None:
    return None


def contains_doctest(num: int = 10) -> int:
    """
    This function contains docstring and doctest
    >>> contains_doctest()
    15
    """
    return num + 5


def test_function() -> None:
    """As this file contains a test function, there should not be a check for
    doctest in any function/class"""
    return None


class ClassTest:
    def __init__(self, num: int) -> None:
        """No point in having doctest in here"""
        self.num = num

    def cls_no_doctest(self) -> int:
        """
        This function contains docstring but no doctest
        """
        return self.num

    # This function do not contain docstring and doctest
    def cls_no_docstring_and_doctest(self) -> int:
        return self.num

    def cls_contains_doctest(self, num: int = 10) -> int:
        """
        This function contains docstring and doctest
        >>> c = ClassTest(5)
        >>> c.cls_contains_doctest()
        15
        """
        return num + self.num
