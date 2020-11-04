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


class ClassTest:
    def __init__(self, num: int) -> None:
        """No point in having doctest in here"""
        self.num = num

    def cls_no_doctest(self) -> None:
        """
        This function contains docstring but no doctest
        """
        return None

    # This function do not contain docstring and doctest
    def cls_no_docstring_and_doctest(self) -> None:
        return None

    def cls_contains_doctest(self, num: int = 10) -> int:
        """
        This function contains docstring and doctest
        >>> cls_contains_doctest()
        15
        """
        return num + 5
