"""
Author: Bruce Lu
Email: lzbgt_AT_icloud.com
"""

import logging
import sys

names = {

}


def get_logger(name, level: int = logging.INFO):
    if name in names:
        return names[name]
    logger = logging.getLogger(name)
    logger.setLevel(level)
    stream_handler = logging.StreamHandler(sys.stdout)
    log_formatter = logging.Formatter(
        "[%(levelname)s %(asctime)s %(threadName)s %(filename)s:%(lineno)d %(funcName)s] %(message)s")
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)
    names[name] = logger
    return logger
