import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="%m-%d %H:%M")

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)

fileHandler = logging.FileHandler("./main.log")
fileHandler.setFormatter(logFormatter)

logger.addHandler(consoleHandler)
logger.addHandler(fileHandler)
