# -*- coding: utf-8 -*-

import sys
import os


commands = {}

class CommandType(type):
    def __init__(cls, name, bases, attrs):
        super(CommandType, cls).__init__(name, bases, attrs)
        name = getattr(cls, name, cls.__name__.lower())
        cls.name = name
        if name != 'command':
            commands[name] = cls


class Command(object):
    """Subclass this class to define new openerp subcommands """
    __metaclass__ = CommandType

    def run(self, args):
        pass


class Help(Command):
    """Display the list of available commands"""

    def run(self, args):
        print "Available commands:\n"
        padding = max([len(k) for k in commands.keys()]) + 2
        for k, v in commands.items():
            print "    %s%s" % (k.ljust(padding, ' '), v.__doc__ or '')
        print "\nUse '%s <command> --help' for individual command help." % sys.argv[0].split(os.path.sep)[-1]

import server

def main():
    command = "server"
    if command in commands:
        o = commands[command]()
        o.run()






























