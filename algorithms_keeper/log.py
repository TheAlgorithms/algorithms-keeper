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

    # Useful for resetting the color according to the log level
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
            eval(f"self.{color.upper()}"),
            eval(f"self.{style.upper()}"),
            msg,
            self.RESET_ALL,
            eval(f"self.{reset.upper()}"),
        ]
        return "".join(msgparts)


Color = AnsiColor()


class CustomFormatter(logging.Formatter):
    # Time is coming directly from Heroku.
    output = "[%(levelname)s] %(message)s"

    LOGGING_FORMAT = {
        logging.DEBUG: Color.DEBUG + output + Color.RESET_ALL,
        logging.INFO: Color.INFO + output + Color.RESET_ALL,
        logging.WARNING: Color.WARNING + output + Color.RESET_ALL,
        logging.ERROR: Color.ERROR + output + Color.RESET_ALL,
        logging.CRITICAL: Color.CRITICAL + output + Color.RESET_ALL,
    }

    def format(self, record):
        log_fmt = self.LOGGING_FORMAT.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        if record.exc_info:
            msg = str(record.msg)
            err = formatter.formatException(record.exc_info)
            if err[-1:] != "\n":
                err += "\n"
            record.msg = msg + "\n" + err
            # Don't print this again.
            record.exc_info = None
        return formatter.format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(stream=sys.stderr)
handler.setFormatter(CustomFormatter())

logger.addHandler(handler)
