import logging
import os
from typing import Any, Dict, MutableMapping

from aiohttp.abc import AbstractAccessLogger
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import StreamResponse

CSI = "\033["

MSG_ARGS_FORMAT = {
    "event": {"color": "green"},
    "ratelimit": {"color": "yellow", "style": "bold"},
    "time_remaining": {"color": "yellow", "style": "bold"},
    "url": {"color": "blue", "style": "underline"},
    "file": {"color": "yellow"},
    "request": {"color": "yellow"},
    "time": {"color": "yellow"},
    "status": {"color": "", "style": "bold"},  # Determined during runtime.
}

STATUS_COLOR = {200: "green", 500: "red"}


def colorcode(code: int) -> str:
    return CSI + str(code) + "m"


def inject_status_color(status: int) -> None:  # pragma: no cover
    """Inject the color of response status in the color format dictionary."""
    assert isinstance(status, int), status
    MSG_ARGS_FORMAT["status"]["color"] = STATUS_COLOR.get(status, "white")


def format_args(
    args: MutableMapping[str, Any], level: str
) -> Dict[str, str]:  # pragma: no cover
    """Inject the color and style according to the specification provided in the
    format dictionary."""
    # We could directly mutate the `args` dictionary but it is better this way in
    # the long run.
    formatted = {}
    for key, value in args.items():
        if key in MSG_ARGS_FORMAT:
            c = MSG_ARGS_FORMAT[key]
            style = "normal" if "style" not in c else c["style"]
            value = Color.inject(str(value), c["color"], style, level)
        formatted[key] = value
    return formatted


class AnsiColor:  # pragma: no cover
    BLACK = colorcode(30)
    RED = colorcode(31)
    GREEN = colorcode(32)
    YELLOW = colorcode(33)
    BLUE = colorcode(34)
    MAGENTA = colorcode(35)
    CYAN = colorcode(36)
    WHITE = colorcode(37)
    RESET = colorcode(39)

    BOLD = colorcode(1)
    DIM = colorcode(2)
    UNDERLINE = colorcode(4)
    NORMAL = colorcode(22)
    RESET_ALL = colorcode(0)

    # Log level format
    DEBUG = DIM
    INFO = DIM
    WARNING = YELLOW
    ERROR = RED
    CRITICAL = MAGENTA + BOLD

    def inject(self, msg: str, color: str, style: str, reset: str) -> str:
        """Inject the color and an optional style to the given message and reset it
        back to being the given log level in 'reset'.

        This method is only to be used when injecting color/style to a submessage.
        """
        msgparts = [
            self.RESET_ALL,
            # Color and style can be in any order.
            getattr(self, color.upper()),
            getattr(self, style.upper()),
            msg,
            self.RESET_ALL,
            getattr(self, reset.upper()),
        ]
        return "".join(msgparts)


Color = AnsiColor()


class CustomAccessLogger(AbstractAccessLogger):  # pragma: no cover

    LOG_FORMAT = '%(logger)s "%(request)s" %(status)s %(time)s'

    def log(self, request: BaseRequest, response: StreamResponse, time: float) -> None:
        """Log the incoming POST request from GitHub."""
        try:
            inject_status_color(response.status)
            self.logger.info(
                self.log_format,
                {
                    "logger": self.logger.name,
                    "request": f"{request.method} {request.path_qs} "
                    f"{request.scheme.upper()}/{request.version.major}."
                    f"{request.version.minor}",
                    "status": f"{response.status}:{response.reason}",
                    "time": f"{str(round(time * 1000))}ms",
                },
            )
        except Exception:
            self.logger.exception(f"Error in logging for {self.logger.name!r} logger.")


class CustomFormatter(logging.Formatter):  # pragma: no cover
    # Time is coming directly from Heroku.
    default_fmt = "[%(levelname)s] %(message)s"

    LOG_LEVEL_FORMAT = {
        "DEBUG": Color.DEBUG + default_fmt + Color.RESET_ALL,
        "INFO": Color.INFO + default_fmt + Color.RESET_ALL,
        "WARNING": Color.WARNING + default_fmt + Color.RESET_ALL,
        "ERROR": Color.ERROR + default_fmt + Color.RESET_ALL,
        "CRITICAL": Color.CRITICAL + default_fmt + Color.RESET_ALL,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Custom formating for the log message.

        If the record contains an exception, then add that to the 'message'. Heroku
        splits the message according to newline and thus the color format will
        disappear, so add the color format after every newline as well.
        """
        custom_fmt = self.LOG_LEVEL_FORMAT.get(record.levelname, self.default_fmt)
        # Inject custom formating to the base class which `self.formatMessage` calls.
        self._style._fmt = custom_fmt
        if record.args and isinstance(record.args, MutableMapping):
            record.args = format_args(record.args, record.levelname)
        msg = record.getMessage()
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if msg[-1:] != "\n":
                msg += "\n"
            msg += record.exc_text
            c = getattr(AnsiColor, record.levelname)
            msg = msg.replace("\n", f"\n{c}")
        if record.stack_info:
            if msg[-1:] != "\n":
                msg += "\n"
            msg += self.formatStack(record.stack_info)
        record.message = msg
        return self.formatMessage(record)


handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
# This is done so that we can change the level directly from Heroku.
loglevel = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=loglevel, handlers=[handler])
# Main logger for the bot.
logger = logging.getLogger(__package__)
