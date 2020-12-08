def no_annotation(num: int):
    """
    This function contains no return annotation
    >>> no_annotation(5)
    10
    """
    return num + 5


def contains_annotation(num: int) -> None:
    """
    This function contains return annotation
    >>> contains_annotation()
    None
    """
    return None


class ClassTest:
    def __init__(self, test: int):
        """This function contatins no return annotation"""
        self.test = test

    def cls_no_annotation(self, num: int):
        """
        This function contains no return annotation
        >>> cls_no_annotation(5)
        10
        """
        return num + 5

    def cls_contains_annotation(self, num: int) -> None:
        """
        This function contains return annotation
        >>> cls_contains_annotation()
        None
        """
        return None
