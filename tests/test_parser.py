import ast
from operator import itemgetter
from pathlib import Path, PurePath

import pytest

from algorithms_keeper.constants import Label
from algorithms_keeper.parser import PullRequestFilesParser, ReviewComment
from algorithms_keeper.utils import File

from .utils import user

DATA_DIRPATH = Path.cwd() / "tests" / "data"

FILE_EXPECTED = (
    ("doctest.py", 4),
    ("return_annotation.py", 3),
    ("descriptive_name.py", 16),
    ("annotation.py", 7),
)

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


def test_review_comment():
    comment = ReviewComment("body", "test.py", 1)
    assert comment.asdict == {
        "body": "body",
        "path": "test.py",
        "line": 1,
        "side": "RIGHT",
    }


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
            "def test_function():\n" "    pass",
            True,
        ),
        (
            "def random():\n" "    pass\n" "\n" "\n" "class TestClass:\n" "    pass",
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
        (get_parser("test.py"), ""),
    ),
)
def test_type_label(parser, expected):
    assert parser.type_label() == expected


@pytest.mark.parametrize(
    "parser, expected",
    (
        (get_parser("test.txt, README.md, scripts/validate.py"), 0),
        (get_parser("project/sol1.py, project/__init__.py"), 1),
        (get_parser("algo.py, test_algo.py, algo_test.py"), 1),
        (get_parser("algo.py, another.py, yetanother.py", "modified"), 0),
    ),
)
def test_files_to_check(parser, expected):
    assert len(parser.files_to_check()) == expected


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
    parser.parse(parser.pr_files[0], source)
    assert not parser.add_labels
    assert not parser.remove_labels
    assert len(parser._pr_record.error) == 1


def test_no_doctest_checking():
    parser = get_parser("contains_testnode.py")
    parser.parse(parser.pr_files[0], get_source("contains_testnode.py"))
    assert not parser.add_labels
    assert not parser.remove_labels
    assert not parser._pr_record.doctest


@pytest.mark.parametrize("filename, expected", FILE_EXPECTED)
def test_individual_files(filename, expected):
    parser = get_parser(filename)
    parser.parse(parser.pr_files[0], get_source(filename))
    assert len(eval(f"parser._pr_record.{filename.split('.')[0]}")) == expected


def test_all_files():
    parser = get_parser(", ".join(map(itemgetter(0), FILE_EXPECTED)))
    expected = 0
    for index, file in enumerate(FILE_EXPECTED):
        parser.parse(parser.pr_files[index], get_source(file[0]))
        expected += file[1]
    assert len(parser.collect_comments()) == expected
    # Test add all labels.
    assert len(parser.add_labels) == 3
    assert not parser.remove_labels


def test_remove_all_labels():
    all_labels = [Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAMES, Label.ANNOTATIONS]
    # As there is a test file, there should not be a check for doctest. Now, all the
    # labels exist and we will be using `doctest.py`, thus the parser should remove
    # all the labels.
    parser = get_parser("doctest.py, test_file.py")
    # Inject all the labels in the pull request labels attribute.
    parser.pr_labels = all_labels
    parser.parse(parser.pr_files[0], get_source("doctest.py"))
    assert len(parser.remove_labels) == 3
    assert not parser.add_labels
