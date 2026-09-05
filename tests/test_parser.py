from pathlib import Path

import pytest

from algorithms_keeper.constants import Label
from algorithms_keeper.parser import PythonParser, rules
from algorithms_keeper.parser.record import PullRequestReviewRecord
from algorithms_keeper.utils import File

from .utils import user

TOTAL_RULES_COUNT: int = len(rules.__all__)

DATA_DIRPATH = Path.cwd() / "tests" / "data"

PR = {"user": {"login": user}, "labels": [], "html_url": "", "url": ""}


# Don't mix this up with `utils.get_file_content`
def get_source(filename: str) -> bytes:
    with Path.open(DATA_DIRPATH / filename) as file:
        file_content = file.read()
    return file_content.encode("utf-8")


def get_parser(filenames: str, status: str = "added") -> PythonParser:
    files = []
    for name in filenames.split(","):
        name = name.strip()  # noqa: PLW2901
        files.append(File(name, Path(name), "", status))
    return PythonParser(files, pull_request=PR)


@pytest.mark.parametrize(
    "parser, expected",
    (
        # Non-python files having prefix `test_` should not be considered.
        (get_parser("test_data.txt, sol1.py"), TOTAL_RULES_COUNT),
        (get_parser("tests/test_file.py, data/no_error.py"), TOTAL_RULES_COUNT - 1),
        (get_parser("data/no_error.py, data/doctest.py"), TOTAL_RULES_COUNT),
    ),
)
def test_contains_testfile(parser: PythonParser, expected: int) -> None:
    assert len(parser._rules) == expected


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
        # Lock files are committed for reproducible CI, so they are valid.
        (get_parser("uv.lock, sol1.py"), ""),
        # ``Dockerfile`` is an accepted extension-less filename.
        (get_parser("Dockerfile, sol1.py"), ""),
        (get_parser(".devcontainer/Dockerfile"), ""),
    ),
)
def test_validate_extension(parser: PythonParser, expected: str) -> None:
    assert parser.validate_extension() == expected


@pytest.mark.parametrize(
    "parser, expected",
    (
        (get_parser("README.md"), Label.DOCUMENTATION),
        (get_parser("README.rst", "modified"), Label.DOCUMENTATION),
        (get_parser("test.py, README.md", "modified"), Label.DOCUMENTATION),
        (get_parser("test.py", "modified"), Label.ENHANCEMENT),
        (get_parser("test.py", "renamed"), Label.ENHANCEMENT),
        (get_parser("test.py", "removed"), Label.ENHANCEMENT),
        # DIRECTORY.md gets updated automatically in every PR.
        (get_parser("sol1.py, DIRECTORY.md"), ""),
        (get_parser("test_file.py"), ""),
    ),
)
def test_type_label(parser: PythonParser, expected: str) -> None:
    assert parser.type_label() == expected


@pytest.mark.parametrize(
    "parser, ignore_modified, expected",
    (
        (get_parser("test.txt, README.md, scripts/validate.py"), True, 0),
        (get_parser("project/sol1.py, project/__init__.py"), True, 1),
        (get_parser("algo.py, test_algo.py, algo_test.py"), True, 1),
        (get_parser("algo.py, another.py, yetanother.py", "modified"), True, 0),
        (get_parser("algo.py, another.py, README.md", "modified"), False, 2),
        (get_parser("algo.py, another.py, README.md", "removed"), False, 2),
        (get_parser("algo.py, another.py, README.md", "renamed"), False, 2),
        (get_parser("algo.py, another.py, README.md"), False, 2),
    ),
)
def test_files_to_check(
    parser: PythonParser, ignore_modified: bool, expected: int
) -> None:
    assert len(list(parser.files_to_check(ignore_modified))) == expected


def test_record_error() -> None:
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
        parser.parse(file, source.encode("utf-8"))
    assert not parser.labels_to_add
    assert not parser.labels_to_remove
    assert len(parser._pr_record._comments) == 1


@pytest.mark.parametrize(
    "filename, expected",
    (
        ("annotation.py", 5),
        ("descriptive_name.py", 8),
    ),
)
def test_lineno_exist(filename: str, expected: int) -> None:
    parser = get_parser(filename)
    for file in parser.files_to_check(True):
        parser.parse(file, get_source(filename))
    assert len(parser._pr_record._comments) == expected
    assert len(parser.labels_to_add) == 1
    assert not parser.labels_to_remove


def test_lineno_exist_multiple_types() -> None:
    # Multiple errors on the same line should result in only one review comment.
    source = "def f(a):\n    return None"
    parser = get_parser("multiple_types.py")
    for file in parser.files_to_check(True):
        parser.parse(file, source.encode("utf-8"))
    assert len(parser._pr_record._comments) == 1
    assert len(parser.labels_to_add) == 3
    assert not parser.labels_to_remove


def test_same_lineno_multiple_source() -> None:
    source = "def f(a):\n    return None"
    parser = get_parser("first_file.py, second_file.py")
    for file in parser.files_to_check(True):
        parser.parse(file, source.encode("utf-8"))
    assert len(parser._pr_record._comments) == 2
    assert len(parser.labels_to_add) == 3
    assert not parser.labels_to_remove


@pytest.mark.parametrize(
    "filename, expected, labels, add_count, remove_count",
    (
        ("doctest.py", 4, [Label.REQUIRE_TEST], 0, 0),
        (
            "return_annotation.py",
            3,
            [Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAME],
            1,
            2,
        ),
        ("descriptive_name.py", 16, [], 1, 0),
        (
            "annotation.py",
            7,
            [Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAME, Label.TYPE_HINT],
            0,
            2,
        ),
        ("doctest.py, return_annotation.py", 7, [Label.TYPE_HINT], 1, 0),
        # As there is a test file, there should not be a check for doctest. Now, all the
        # labels exist and we will be using `doctest.py`, thus the parser should remove
        # all the labels.
        (
            "doctest.py, test_file.py",
            0,
            [Label.REQUIRE_TEST, Label.DESCRIPTIVE_NAME, Label.TYPE_HINT],
            0,
            3,
        ),
    ),
)
def test_combinations(
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    expected: int,
    labels: list[str],
    add_count: int,
    remove_count: int,
) -> None:
    # We will set this to ``False`` only for the tests as we want to know whether the
    # parser_old detected all the missing requirements.
    monkeypatch.setattr(PullRequestReviewRecord, "_lineno_exist", lambda *args: False)
    parser = get_parser(filename)
    parser.pr_labels = labels
    for file in parser.files_to_check(True):
        parser.parse(file, get_source(file.name))
    assert len(parser._pr_record._comments) == expected
    assert len(parser.labels_to_add) == add_count
    assert len(parser.labels_to_remove) == remove_count


@pytest.mark.parametrize("filename", ("web_programming/example.py", "other/example.py"))
def test_doctest_filepath(filename: str) -> None:
    parser = get_parser(filename)
    for file in parser.files_to_check(True):
        parser.parse(file, b"def example() -> None:\n    pass\n")
    if filename.startswith("web_programming/"):
        assert parser.collect_comments() == []
        assert parser.labels_to_add == []
    else:
        assert parser.labels_to_add == [Label.REQUIRE_TEST]
        assert parser.collect_comments() == [
            {
                "body": (
                    "As there is no test file in this pull request nor any test "
                    f"function or class in the file `{filename}`, "
                    "please provide doctest for "
                    "the function `example`"
                ),
                "path": filename,
                "line": 1,
                "side": "RIGHT",
            }
        ]


@pytest.mark.parametrize(
    "directive",
    ("# lint-ignore", "# lint-fixme", "# lint-ignore: RequireTypeHintRule", "# noqa"),
)
def test_review_does_not_honor_suppressions(directive: str) -> None:
    parser = get_parser("example.py")
    source = f"{directive}\ndef f(a):  {directive}\n    return None\n".encode()
    for file in parser.files_to_check(True):
        parser.parse(file, source)
    assert set(parser.labels_to_add) == {
        Label.REQUIRE_TEST,
        Label.TYPE_HINT,
        Label.DESCRIPTIVE_NAME,
    }
    comments = parser.collect_comments()
    assert len(comments) == 1
    assert comments[0]["path"] == "example.py"
    assert comments[0]["line"] == 2


def test_rule_state_is_isolated_between_files() -> None:
    parser = get_parser("tested.py, untested.py")
    sources = {
        "tested.py": b'""">>> example()\n"""\ndef example() -> None:\n    pass\n',
        "untested.py": b"def example() -> None:\n    pass\n",
    }
    for file in parser.files_to_check(True):
        parser.parse(file, sources[file.name])
    assert parser.labels_to_add == [Label.REQUIRE_TEST]
    assert [comment["path"] for comment in parser.collect_comments()] == ["untested.py"]


def test_builtin_fixit_rules_are_not_enabled() -> None:
    parser = get_parser("example.py")
    for file in parser.files_to_check(True):
        # Fixit's built-in CompareSingletonPrimitivesByIs would report this.
        parser.parse(file, b"example = None == None\n")
    assert parser.collect_comments() == []
    assert parser.labels_to_add == []
