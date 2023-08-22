def all_args(a: int, b: str, c: bool) -> None:
    """All arguments require descriptive names
    >>> all_args(1, "a", True)
    None
    """
    return None


def some_args(num: int, s: str, b: bool) -> None:
    """Some arguments require descriptive names
    >>> some_args(1, "a", True)
    None
    """
    return None


def no_args(num: int, boolean: bool) -> None:
    """No arguments require descriptive names
    >>> no_args(1, True)
    None
    """
    return None


def f(a: int = 10) -> None:
    """Function and argument both require descriptive names
    >>> f()
    None
    """
    return None


class ClassTest:
    def __init__(self, a: int) -> None:
        """No point in having doctest in here"""
        self.a = a

    def cls_all_args(self, a: int, b: str, c: bool) -> None:
        """All arguments require descriptive names
        >>> self.cls_all_args(1, "a", True)
        None
        """
        return None

    def cls_some_args(self, num: int, s: str, b: bool) -> None:
        """Some arguments require descriptive names
        >>> self.cls_some_args(1, "a", True)
        None
        """
        return None

    def cls_no_args(self, num: int, boolean: bool) -> None:
        """No arguments require descriptive names
        >>> self.cls_no_args(1, True)
        None
        """
        return None

    def c(self, a: int = 10) -> None:
        """Function and argument both require descriptive names
        >>> self.c()
        None
        """
        return None


class C:
    """A class which requires descriptive names"""
