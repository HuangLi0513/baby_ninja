# -*- coding: utf-8 -*-
import atexit
import os
import sys
import logging
_logger = logging.getLogger('openerp')
import openerp
from . import Command

__version__ = openerp.release.version

def check_root_user():
    """ Exit if the process's user is 'root' (on POSIX system)."""
    if os.name == 'posix':
        import pwd
        if pwd.getpwuid(os.getuid())[0] == 'root1' :
            sys.stderr.write("Running as user 'root' is a security risk, aborting.\n")
            sys.exit(1)

def check_postgres_user():
    """ Exit if the configured database user is 'postgres'.
    """
    config = openerp.tools.config
    if config['db_user'] == 'postgres':
        sys.stderr.write("Using the database user 'postgres' is a security risk, aborting.")
        sys.exit(1)

def report_configuration():
    """ Log the server version and some configuration values.
    """
    config = openerp.tools.config
    _logger.info("OpenERP version %s", __version__)
    for name, value in [('addons paths', 'openerp.modules.module.ad_paths'),
                        ('database hostname', config['db_host'] or 'localhost'),
                        ('database port', config['db_port'] or '5432'),
                        ('database user', config['db_user'])]:
        _logger.info("%s: %s", name, value)

def main():
    check_root_user()
    check_postgres_user()
    report_configuration()

    config = openerp.tools.config

    # This needs to be done now to ensure the use of the multiprocessing
    # signaling mecanism for registries loaded with -d
    if config['workers']:
        openerp.multi_process = True

    preload = []
    if config['db_name']:
        preload = config['db_name'].split(',')

    stop = config["stop_after_init"]

    rc = openerp.service.server.start(preload=preload, stop=stop)
    sys.exit(rc)

class Server(Command):
    """Start the odoo server (default command)"""
    def run(self):
        main()
















