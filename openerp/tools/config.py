# -*- coding: utf-8 -*-

import os
import sys
import ConfigParser

class configmanager(object):
    def __init__(self, fname=None):
        self.options = {
            'admin_passwd': 'admin',
        }

        self.config_file = fname

        self._parse_config()

    def _parse_config(self):
        rcfilepath = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), 'openerp-server.conf')
        self.rcfile = os.path.abspath(
            self.config_file or rcfilepath)
        self.load()

        if isinstance(self.options['log_handler'], basestring):
            self.options['log_handler'] = self.options['log_handler'].split(',')

    def load(self):
        p = ConfigParser.ConfigParser()
        try:
            p.read([self.rcfile])
            for (name,value) in p.items('options'):
                if value=='True' or value=='true':
                    value = True
                if value=='False' or value=='false':
                    value = False
                self.options[name] = value
        except IOError:
            pass
        except ConfigParser.NoSectionError:
            pass

    def get(self, key, default=None):
        return self.options.get(key, default)

    def __getitem__(self, key):
        if key in self.options:
            return self.options[key]
        else:
            return None

    def __setitem__(self, key, value):
        self.options[key] = value

config = configmanager()

























