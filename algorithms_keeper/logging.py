import logging

logger = logging.getLogger("algorithms_keeper")
logger.setLevel("INFO")

handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)
