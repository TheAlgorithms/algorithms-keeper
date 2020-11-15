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


color = AnsiColor()


class CustomFormatter(logging.Formatter):
    # Time is coming directly from Heroku.
    output = "[%(levelname)s] %(message)s"

    LOGGING_FORMAT = {
        logging.DEBUG: color.DIM + output + color.RESET_ALL,
        logging.INFO: color.DIM + output + color.RESET_ALL,
        logging.WARNING: color.YELLOW + output + color.RESET_ALL,
        logging.ERROR: color.RED + output + color.RESET_ALL,
        logging.CRITICAL: color.RED + color.BOLD + output + color.RESET_ALL,
    }

    def format(self, record):
        log_fmt = self.LOGGING_FORMAT.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(stream=sys.stderr)
handler.setFormatter(CustomFormatter())

logger.addHandler(handler)
