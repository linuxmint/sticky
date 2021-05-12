#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import dbus
import names
import logging


class ArgumentParserBuilder(object):

    def __init__(self, parser):
        self._last_parser = parser
        self._last_subparsers = None
        self._parse_stack = []

    def __enter__(self, *args):
        global logger
        logger.debug(f'__enter__: {args}')

        self._parse_stack.append((self._last_parser, self._last_subparsers))

        return self

    def __exit__(self, *args):
        global logger
        logger.debug(f'__exit__: {args}')
        self._parse_stack.pop()

    def add_argument(self, *args, **kwargs):
        parser = self._parse_stack[-1][0]

        parser.add_argument(*args, **kwargs)

    def _get_parent_parsers(self):
        parser, subparsers = self._parse_stack[-1]

        if not subparsers:
            subparsers = parser.add_subparsers(dest='command', required=True, help='Command to run')
            self._parse_stack[-1] = (parser, subparsers)

        return parser, subparsers

    def add_command(self, command_name, callback=None):
        global logger
        logger.info(f'Adding command: {command_name}')

        parent_parser, parent_subparsers = self._get_parent_parsers()

        parser = parent_subparsers.add_parser(command_name)

        parent_command = parent_parser.get_default('command')

        if parent_command:
            command = parent_command + '.'
        else:
            command = ''

        command += command_name

        defaults = {
            'command': command,
            'callback': callback,
        }

        parser.set_defaults(**defaults)

        self._last_parser = parser
        self._last_subparsers = None

        return self


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbosity', '-v', action='count', default=0, help='Verbosity level (up to 4 v\'s)')

    with ArgumentParserBuilder(parser) as b:
        with b.add_command('note'):
            b.add_command('activate')
            b.add_command('hide')
            # b.add_command('toggle')
            b.add_command('new')

        with b.add_command('group'):
            b.add_command('new')
            with b.add_command('change'):
                b.add_argument('group_name')

        with b.add_command('manager'):
            b.add_command('open')

        with b.add_command('settings'):
            b.add_command('open')

        with b.add_command('shortcuts'):
            b.add_command('open')

        b.add_command('quit')

    return parser.parse_args()


def main():
    global logger
    logger = logging.getLogger(__name__)
    # logging.basicConfig(level='DEBUG')

    args = parse_command_line()

    _to_logging_verbosity_level = {
        0: "CRITICAL",
        1: "ERROR",
        2: "WARNING",
        3: "INFO",
        4: "DEBUG",
    }

    logging.basicConfig(level=_to_logging_verbosity_level[args.verbosity])

    call_dbus_method(args)


def error(message, exit_code=1):
    logger.critical(message)
    sys.exit(exit_code)


def call_dbus_method(args):
    global logger
    logger.info(f'Received args={args}')

    _command_line_to_dbus_method_name = {
        'note.activate': ('activate_notes', lambda args: ()),
        'note.hide': ('hide_notes', lambda args: ()),
        'note.new': ('new_note', lambda args: ()),
        'group.new': ('new_group', lambda args: ()),
        'group.change': ('change_visible_note_group', lambda args: (args.group_name, )),
        'manager.open': ('open_manager', lambda args: ()),
        'settings.open': ('open_settings_window', lambda args: ()),
        'shortcuts.open': ('open_keyboard_shortcuts', lambda args: ()),
        'quit': ('quit_app', lambda args: ()),
    }

    method_name, args_getter = _command_line_to_dbus_method_name.get(args.command)

    if not method_name:
        error(f'ERROR: Method name not found in bus ({args.command})', 1)

    bus = dbus.SessionBus()
    sticky_service = bus.get_object(bus_name=names.bus_name, object_path=names.object_path)

    method = sticky_service.get_dbus_method(method_name, names.bus_name)

    method_args = args_getter(args)

    logger.debug(f'Calling "{method_name}" with "{method_args}"')

    method(*method_args)

    return 0

if __name__ == '__main__':
    sys.exit(main())
