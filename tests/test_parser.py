import ast
from pathlib import Path, PurePath

import pytest

from algorithms_keeper.constants import Label
from algorithms_keeper.parser import PullRequestFilesParser, PullRequestReviewRecord
from algorithms_keeper.utils import File

from .utils import user

DATA_DIRPATH = Path.cwd() / "tests" / "data"

PR = {"user": {"login": user}, "labels": [], "html_url": "", "url": ""}


# Don't mix this up with `utils.get_file_content`
def get_source(filename: str) -> str:
    with open(DATA_DIRPATH / filename) as file:
        file_content = file.read()
    return file_content


def get_parser(filenames: str, status: str = "added") -> PullRequestFilesParser:
    files = []
    for name in filenames.split(","):
        name = name.strip()
        files.append(File(name, PurePath(name), "", status))
    return PullRequestFilesParser(files, pull_request=PR)


@pytest.mark.parametrize(
    "parser, expected",
    (
        (get_parser("tests/test_file.py, data/no_error.py"), True),
        (get_parser("data/no_error.py, data/doctest.py"), False),
    ),
)
def test_contains_testfile(parser, expected):
    assert parser._skip_doctest is expected


@pytest.mark.parametrize(
    "source, expected",
    (
        (
            "def no_test_node():\n"
            "    pass\n"
            "\n"
            "\n"
            "class NoTestNode:\n"
            "    pass",
            False,
        ),
        (
            "def test_function():\n    pass",
            True,
        ),
        (
            "def random():\n    pass\n\n\nclass TestClass:\n    pass",
            True,
        ),
    ),
)
def test_contains_testnode(source, expected):
    mod = ast.parse(source)
    assert PullRequestFilesParser._contains_testnode(mod) is expected


@pytest.mark.parametrize(
    "parser, expected",
    (
        (get_parser(".gitignore"), ""),
        (get_parser("test/.gitignore"), "test/.gitignore"),
        (get_parser("extensionless"), "extensionless"),
        (get_parser(".github/CODEOWNERS, test/CODEOWNERS"), "test/CODEOWNERS"),
        (
            get_parser("test/test.html, test/test.cpp, test/test.py"),
            "test/test.html, test/test.cpp",
        ),
    ),
)
def test_validate_extension(parser, expected):
    assert parser.validate_extension() == expected


@pytest.mark.parametrize(
    "parser, expected",
    (
        (get_parser("README.md"), Label.DOCUMENTATION),
        (get_parser("README.rst", "modified"), Label.DOCUMENTATION),
        (get_parser("test.py, README.md", "modified"), Label.DOCUMENTATION),
        (get_parser("test.py", "modified"), Label.ENHANCEMENT),
        # DIRECTORY.md gets updated automatically in every PR.
        (get_parser("sol1.py, DIRECTORY.md"), ""),
        (get_parser("test.py"), ""),
    ),
)
def test_type_label(parser, expected):
    assert parser.type_label() == expected


@pytest.mark.parametrize(
    "parser, ignore_modified, expected",
    (
        (get_parser("test.txt, README.md, scripts/validate.py"), True, 0),
        (get_parser("project/sol1.py, project/__init__.py"), True, 1),
        (get_parser("algo.py, test_algo.py, algo_test.py"), True, 1),
        (get_parser("algo.py, another.py, yetanother.py", "modified"), True, 0),
        (get_parser("algo.py, another.py, README.md", "modified"), False, 2),
        (get_parser("algo.py, another.py, README.md"), False, 2),
    ),
)
def test_files_to_check(parser, ignore_modified, expected):
    assert len(list(parser.files_to_check(ignore_modified))) == expected


def test_record_error():
    source = (
        "def valid_syntax() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def invalid_syntax() -> None:\n"
        "return None"
    )
    parser = get_parser("invalid_syntax.py")
    for file in parser.files_to_check(True):
        parser.parse(file, source)
    assert not parser.add_labels
    assert not parser.remove_labels
    assert len(parser._pr_record._comments) == 1


def test_no_doctest_checking():
    parser = get_parser("contains_testnode.py")
    for file in parser.files_to_check(True):
        parser.parse(file, get_source("contains_testnode.py"))
    assert not parser.add_labels
    assert not parser.remove_labels
    assert not parser._pr_record._comments


@pytest.mark.parametrize(
    "filename, expected",
    (
        ("annotation.py", 5),
        ("descriptive_name.py", 8),
    ),
)
def test_lineno_exist(filename, expected):
    parser = get_parser(filename)
    for file in parser.files_to_check(True):
        parser.parse(file, get_source(filename))
    assert len(parser._pr_record._comments) == expected
    assert len(parser.add_labels) == 1
    assert not parser.remove_labels


def test_lineno_exist_multiple_types():
    # Multiple errors on the same line should result in only one review comment.
    source = "def f(a):\n    return None"
    parser = get_parser("multiple_types.py")
    for file in parser.files_to_check(True):
        parser.parse(file, source)
    assert len(parser._pr_record._comments) == 1
    assert len(parser.add_labels) == 3
    assert not parser.remove_labels


def test_same_lineno_multiple_source():
    source = "def f(a):\n    return None"
    parser = get_parser("first_file.py, second_file.py")
    for file in parser.files_to_check(True):
        parser.parse(file, source)
    assert len(parser._pr_record._comments) == 2
    assert len(parser.add_labels) == 3
    assert not parser.remove_labels


@pytest.mark.parametrize(
    "filename, expected, labels, add_count, remove_count",
    (
        ("doctest.py", 4, (Label.REQUIRE_TEST,), 0, 0),
        (
            "return_annotation.py",
            3,
            (Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAME),
            1,
            2,
        ),
        ("descriptive_name.py", 16, (), 1, 0),
        (
            "annotation.py",
            7,
            (Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAME, Label.TYPE_HINT),
            0,
            2,
        ),
        ("doctest.py, return_annotation.py", 7, (Label.TYPE_HINT,), 1, 0),
        # As there is a test file, there should not be a check for doctest. Now, all the
        # labels exist and we will be using `doctest.py`, thus the parser should remove
        # all the labels.
        (
            "doctest.py, test_file.py",
            0,
            (Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAME, Label.TYPE_HINT),
            0,
            3,
        ),
    ),
)
def test_combinations(monkeypatch, filename, expected, labels, add_count, remove_count):
    # We will set this to ``False`` only for the tests as we want to know whether the
    # parser detected all the missing requirements.
    monkeypatch.setattr(PullRequestReviewRecord, "_lineno_exist", lambda *args: False)
    parser = get_parser(filename)
    parser.pr_labels = labels
    for file in parser.files_to_check(True):
        parser.parse(file, get_source(file.name))
    assert len(parser._pr_record._comments) == expected
    assert len(parser.add_labels) == add_count
    assert len(parser.remove_labels) == remove_count
