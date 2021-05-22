import logging
from logging.handlers import TimedRotatingFileHandler


def setup_logging():
    """ Set up logging for scottyhook """
    logger = logging.getLogger()
    handler = TimedRotatingFileHandler("scottyhook.log", when="W6", backupCount=4)

    # Set Logging Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("Logging Enabled")
    return logger
