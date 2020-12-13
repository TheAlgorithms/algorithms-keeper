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


class ClassContainingDoctest:
    """This class contains doctest in its class-level docstring.

    >>> obj = ClassContainingDoctest(10)
    >>> obj.value
    10
    >>> obj.value = 11
    >>> obj.value
    11
    >>> await obj.cls_method()
    None
    """

    def __init__(self, value: int) -> None:
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, val: int) -> None:
        self._value = val

    def method(self) -> None:
        return None

    async def cls_method(self) -> None:
        return None
