import logging
from typing import Any, Dict, MutableMapping

CSI = "\033["


def colorcode(code: int) -> str:
    return CSI + str(code) + "m"


class AnsiColor:
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


class CustomFormatter(logging.Formatter):
    # Time is coming directly from Heroku.
    default_fmt = "[%(levelname)s]::%(name)s %(message)s"

    LOGGING_FORMAT = {
        "DEBUG": Color.DEBUG + default_fmt + Color.RESET_ALL,
        "INFO": Color.INFO + default_fmt + Color.RESET_ALL,
        "WARNING": Color.WARNING + default_fmt + Color.RESET_ALL,
        "ERROR": Color.ERROR + default_fmt + Color.RESET_ALL,
        "CRITICAL": Color.CRITICAL + default_fmt + Color.RESET_ALL,
    }

    MSG_ARGS_FORMAT = {
        "event": {"color": "green"},
        "ratelimit": {"color": "yellow", "style": "bold"},
        "time_remaining": {"color": "yellow", "style": "bold"},
        "url": {"color": "blue"},
        "file": {"color": "yellow"},
    }

    def format(self, record: logging.LogRecord) -> str:
        """Custom formating for the log message.

        If the record contains an exception, then add that to the 'message'. Heroku
        splits the message according to newline and thus the color format will
        disappear, so add the color format after every newline as well.
        """
        custom_fmt = self.LOGGING_FORMAT.get(record.levelname, self.default_fmt)
        # Inject custom formating to the base class which `self.formatMessage` calls.
        self._style._fmt = custom_fmt
        if record.args and isinstance(record.args, MutableMapping):
            record.args = self.format_args(record.args, record.levelname)
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
        record.message = msg
        return self.formatMessage(record)

    def format_args(self, args: MutableMapping[str, Any], level: str) -> Dict[str, str]:
        """Inject the color and style according to the specification provided in the
        format dictionary."""
        # We could directly mutate the `args` dictionary but it is better this way in
        # the long run.
        formatted = {}
        for key, value in args.items():
            if key in self.MSG_ARGS_FORMAT:
                c = self.MSG_ARGS_FORMAT[key]
                style = "normal" if "style" not in c else c["style"]
                value = Color.inject(str(value), c["color"], style, level)
            formatted[key] = value
        return formatted


handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())

logging.basicConfig(level=logging.DEBUG, handlers=[handler])

logger = logging.getLogger(__package__)
