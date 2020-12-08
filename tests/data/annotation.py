def all_annotations(num, test) -> None:
    """All arguments require annotations
    >>> no_annotations(1, "a")
    None
    """
    return None


def some_annotations(num: int, test) -> None:
    """Some arguments require annotations
    >>> some_args(1, "a")
    None
    """
    return None


def no_annotations(num: int, boolean: bool) -> None:
    """No arguments require annotations
    >>> no_args(1, True)
    None
    """
    return None


class ClassTest:
    def __init__(self, num) -> None:
        """__init__ requires annotation"""
        self.num = num

    def cls_all_annotations(self, num, test) -> None:
        """All arguments require annotations
        >>> cls_no_annotations(1, "a")
        None
        """
        return None

    def cls_some_annotations(self, num: int, test) -> None:
        """Some arguments require annotations
        >>> cls_some_annotations(1, "a")
        None
        """
        return None

    def cls_no_annotations(self, num: int, boolean: bool) -> None:
        """No arguments require annotations
        >>> cls_no_annotations(1, True)
        None
        """
        return None
