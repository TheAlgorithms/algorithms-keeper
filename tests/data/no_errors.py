def no_error_func(num: int, name: str, outcome: bool) -> None:
    """No error function
    >>> all_args(1, "a", True)
    None
    """
    return None


def helper(limit: int = 10) -> None:
    """Helper function
    >>> helper()
    None
    """
    return None


class ClassTest:
    def __init__(self, start: int) -> None:
        """No point in having doctest in here"""
        self.start = start

    def cls_no_error_func(self, num: int, name: str, outcome: bool) -> None:
        """No error function
        >>> all_args(1, "a", True)
        None
        """
        return None

    def cls_helper(self, limit: int = 10) -> None:
        """Helper function
        >>> helper()
        None
        """
        return None
