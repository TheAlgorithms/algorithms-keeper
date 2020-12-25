from logging import Logger
from typing import Any, Collection, Iterable, List, Mapping, Set

from algorithms_keeper.constants import Label
from algorithms_keeper.log import logger as main_logger
from algorithms_keeper.utils import File

# These files are updated automatically by a GitHub action in almost every pull request.
IGNORE_FILES_FOR_TYPELABEL: Set[str] = {"DIRECTORY.md"}


class BaseFilesParser:
    """A base parser for all the pull request files.

    This class should be subclassed to fill the appropriate data for the two constants:
    ``DOCS_EXTENSIONS`` and ``ACCEPTED_EXTENSIONS`` as per the language repository.
    """

    pr_labels: List[str]
    pr_html_url: str
    logger: Logger

    DOCS_EXTENSIONS: Collection[str] = ()
    ACCEPTED_EXTENSIONS: Collection[str] = ()

    def __init__(
        self,
        pr_files: Iterable[File],
        pull_request: Mapping[str, Any],
        logger: Logger = main_logger,
    ) -> None:
        # A pull request object for easy access.
        self.pr = pull_request
        self.pr_files = pr_files
        self.pr_labels = [label["name"] for label in pull_request["labels"]]
        self.pr_html_url = pull_request["html_url"]

        # By providing the logger to the class, we won't have to log anything from the
        # pull requests module. Defaults to ``algorithms_keeper.log.logger``
        self.logger = logger

    def validate_extension(self) -> str:
        """Check pull request files extension. Returns an empty string if all files are
        valid otherwise a comma separated string containing the filepaths.

        A file is considered invalid if:

        - It is extensionless and is not a dotfile. NOTE: Files present only in the
          root directory will be checked for dotfile.
        - File extension is not accepted in the repository, defined in the
          `ACCEPTED_EXTENSIONS` constant.

        NOTE: Extensionless files will be considered valid only if it is present in
        the ".github" directory. Eg: ".github/CODEOWNERS"
        """
        invalid_filepath = []
        for file in self.pr_files:
            filepath = file.path
            if not filepath.suffix:
                if ".github" not in filepath.parts:
                    if filepath.parent.name:
                        invalid_filepath.append(file.name)
                    # Dotfiles are not considered as invalid if they are present in the
                    # root of the repository
                    elif not filepath.name.startswith("."):
                        invalid_filepath.append(file.name)
            elif filepath.suffix not in self.ACCEPTED_EXTENSIONS:
                invalid_filepath.append(file.name)
        invalid_files = ", ".join(invalid_filepath)
        if invalid_files:
            self.logger.info(
                "Invalid file(s) [%(file)s]: %(url)s",
                {"file": invalid_files, "url": self.pr_html_url},
            )
        return invalid_files

    def type_label(self) -> str:
        """Determine the type of the given pull request and return an appropriate
        label for it. Returns an empty string if the type is not programmed or the label
        already exists on the pull request.

        **documentation**: Contains a file with an extension from ``DOCS_EXTENSIONS``

        **enhancement**: Some/all files were *modified*

        NOTE: These two types are mutually exclusive which means a modified docs file
        will be labeled **documentation** and not **enhancement**.
        """
        label = ""
        for file in self.pr_files:
            if file.path.suffix in self.DOCS_EXTENSIONS:
                if file.path.name not in IGNORE_FILES_FOR_TYPELABEL:
                    label = Label.DOCUMENTATION
                    break
            elif file.status == "modified":
                label = Label.ENHANCEMENT
        return label if label not in self.pr_labels else ""
