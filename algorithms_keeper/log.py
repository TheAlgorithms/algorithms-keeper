import logging
import sys

CSI = "\033["


def colorcode(code):
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

    def inject(
        self, msg: str, color: str, style: str = "normal", *, reset: str = "info"
    ) -> str:
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
    output = "[%(levelname)s] %(message)s"

    LOGGING_FORMAT = {
        "DEBUG": Color.DEBUG + output + Color.RESET_ALL,
        "INFO": Color.INFO + output + Color.RESET_ALL,
        "WARNING": Color.WARNING + output + Color.RESET_ALL,
        "ERROR": Color.ERROR + output + Color.RESET_ALL,
        "CRITICAL": Color.CRITICAL + output + Color.RESET_ALL,
    }

    def format(self, record):
        """Custom formating for the log message.

        If the record contains an exception, then add that to the 'message'. Heroku
        splits the message according to newline and thus the color format will
        disappear, so add the color format after every newline as well.
        """
        log_fmt = self.LOGGING_FORMAT.get(record.levelname)
        formatter = logging.Formatter(log_fmt)
        msg = record.getMessage()
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = formatter.formatException(record.exc_info)
        if record.exc_text:
            if msg[-1:] != "\n":
                msg += "\n"
            msg += record.exc_text
            c = getattr(AnsiColor, record.levelname)
            msg = msg.replace("\n", f"\n{c}")
        record.message = msg
        return formatter.formatMessage(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(stream=sys.stderr)
handler.setFormatter(CustomFormatter())

logger.addHandler(handler)
