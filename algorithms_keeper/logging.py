import logging

logger = logging.getLogger(__name__)
logger.setLevel("INFO")
handler = logging.StreamHandler()
logger.addHandler(handler)
