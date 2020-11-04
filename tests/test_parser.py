from pathlib import Path

import pytest

from algobot.constants import Label
from algobot.parser import SEP, PullRequestFilesParser

DATA_DIRPATH = Path.cwd() / "tests" / "data"

FILE_EXPECTED = (
    ("require_doctest.py", 4),
    ("require_return_annotation.py", 3),
    ("require_descriptive_names.py", 16),
    ("require_annotations.py", 8),
)


# Don't mix this up with `utils.get_file_content`
def get_file_code(filename: str) -> str:
    with open(DATA_DIRPATH / filename) as file:
        file_content = file.read()
    return file_content


def get_parser_total(parser: PullRequestFilesParser) -> int:
    return (
        len(parser._require_annotations)
        + len(parser._require_descriptive_names)
        + len(parser._require_doctest)
        + len(parser._require_return_annotation)
    )


@pytest.mark.parametrize("filename, expected", FILE_EXPECTED)
def test_individual_files(filename, expected):
    code = get_file_code(filename)
    parser = PullRequestFilesParser()
    parser.parse_code(filename, code)
    attr = filename.split(".")[0]
    assert len(eval(f"parser._{attr}")) == expected


def test_all_files():
    parser = PullRequestFilesParser()
    expected = 0
    for filename, count in FILE_EXPECTED:
        code = get_file_code(filename)
        parser.parse_code(filename, code)
        expected += count
    assert get_parser_total(parser) == expected


def test_skip_doctest():
    filename = "require_doctest.py"
    parser = PullRequestFilesParser()
    assert parser.skip_doctest is False
    parser.skip_doctest = True
    assert parser.skip_doctest is True
    code = get_file_code(filename)
    parser.parse_code(filename, code)
    assert get_parser_total(parser) == 0


@pytest.mark.parametrize(
    "cls_name, func_name, arg_name, expected",
    (
        (None, None, None, "`test.py`"),
        ("TestClass", None, None, f"`test.py{SEP}TestClass`"),
        (None, "test", None, f"`test.py{SEP}test`"),
        (None, None, "num", f"`test.py{SEP}num`"),
        ("TestClass", "func", None, f"`test.py{SEP}TestClass{SEP}func`"),
        ("TestClass", None, "cls_var", f"`test.py{SEP}TestClass{SEP}cls_var`"),
        (None, "func", "arg", f"`test.py{SEP}func{SEP}arg`"),
        (
            "TestClass",
            "method",
            "param",
            f"`test.py{SEP}TestClass{SEP}method{SEP}param`",
        ),
    ),
)
def test_node_path(cls_name, func_name, arg_name, expected):
    parser = PullRequestFilesParser()
    parser._filename = "test.py"
    assert (
        parser._node_path(cls_name=cls_name, func_name=func_name, arg_name=arg_name)
        == expected
    )


def test_add_all_labels():
    parser = PullRequestFilesParser()
    for filename, _ in FILE_EXPECTED:
        code = get_file_code(filename)
        parser.parse_code(filename, code)
    add, remove = parser.labels_to_add_and_remove([])
    assert add == [Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAMES, Label.ANNOTATIONS]
    assert remove == []


def test_remove_all_labels():
    parser = PullRequestFilesParser()
    all_labels = [Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAMES, Label.ANNOTATIONS]
    add, remove = parser.labels_to_add_and_remove(all_labels)
    assert add == []
    assert remove == all_labels


def test_add_few_labels():
    parser = PullRequestFilesParser()
    for i in range(2):
        filename = FILE_EXPECTED[i][0]
        code = get_file_code(filename)
        parser.parse_code(filename, code)
    assert get_parser_total(parser) == 7
    add, remove = parser.labels_to_add_and_remove([Label.REQUIRE_TEST])
    assert add == [Label.ANNOTATIONS]
    assert remove == []


def test_and_and_remove_labels():
    parser = PullRequestFilesParser()
    for i in range(1, 3):
        filename = FILE_EXPECTED[i][0]
        code = get_file_code(filename)
        parser.parse_code(filename, code)
    assert get_parser_total(parser) == 19
    add, remove = parser.labels_to_add_and_remove([Label.REQUIRE_TEST])
    assert add == [Label.DESCRIPTIVE_NAMES, Label.ANNOTATIONS]
    assert remove == [Label.REQUIRE_TEST]
