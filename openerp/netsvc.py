# -*- coding: utf-8 -*-

import logging
import logging.handlers
import os
import sys
import threading

import tools

_logger = logging.getLogger(__name__)


class DBFormatter(logging.Formatter):
    def format(self, record):
        record.pid = os.getpid()
        record.dbname = getattr(threading.currentThread(), 'dbname', '?')
        return logging.Formatter.format(self, record)

_logger_init = False
def init_logger():
    global _logger_init
    if _logger_init:
        return
    _logger_init = True

    # create a format for log messages and dates
    format = '%(asctime)s %(pid)s %(levelname)s %(dbname)s %(name)s: %(message)s'

    handler = logging.StreamHandler(sys.stdout)
    formatter = DBFormatter(format)
    handler.setFormatter(formatter)

    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel('DEBUG')
    _logger.debug('logger inited')

init_logger()
