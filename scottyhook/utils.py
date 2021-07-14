import logging
from logging.handlers import TimedRotatingFileHandler
import requests
import time


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


def exp_backoff(max_retries=10, wait_time=0.5, exception=requests.exceptions.HTTPError):
    def rwb(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exception:
                    attempts += 1
                    if attempts <= max_retries:
                        time.sleep(wait_time * 2 ** attempts)
                    else:
                        raise

        return wrapper

    return rwb


@exp_backoff
def get_with_backoff(*args, **kwargs):
    resp = requests.get(*args, **kwargs)
    resp.raise_for_status()
    return resp

