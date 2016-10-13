import argparse
import curses
from curses.textpad import Textbox, rectangle
from functools import partial
import json
from os.path import expanduser
from time import sleep

from tupler.tupler_zulip_client import Credentials, Events, message_loop, \
    send_private_message, send_stream_message


def _get_credentials(file_name):
    with open(expanduser(file_name)) as credentials_file:
        credentials = json.loads(credentials_file.read())
        return Credentials(**credentials)


def _should_print_component(message, prev_message, component):
    if prev_message is None:
        return True
    component, prev_component = [m.__getattribute__(component)
                                 for m in [message, prev_message]]
    if component == prev_component:
        return False
    return True


def _display_message(window, message, previous_message=None):
    should_print = partial(_should_print_component, message, previous_message)
    if should_print('sender'):
        window.addstr("{}\n".format(message.sender), curses.color_pair(2))
    if not isinstance(message.recipient, list):  # Not a private message
        should_print_recipient = should_print('recipient')
        should_print_subject = should_print('subject')
        if should_print_recipient:
            window.addstr(message.recipient, curses.color_pair(3))
        if should_print_recipient and should_print_subject:
            window.addstr(" > ")
        if should_print_subject:
            window.addstr(message.subject, curses.color_pair(4))
        if should_print_recipient or should_print_subject:
            window.addstr("\n")
    window.addstr("{}\n".format(message.content))


def _initialize_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_BLUE, -1)


def _message_mode(window, credentials, message_function, message_type):
    window.clear()
    window.nodelay(False)
    window.addstr(0, 0, ("Enter {} message, delimit with new lines:"
                         " (hit Ctrl-G to send)").format(message_type))

    editwin = curses.newwin(5, 30, 2, 1)
    rectangle(window, 1, 0, 7, 32)
    window.refresh()

    box = Textbox(editwin)
    box.edit()

    # Get resulting contents
    message = box.gather()
    components = message.strip().split("\n")
    message_function(credentials, *components)

    window.clear()
    window.nodelay(True)


def _private_message_mode(window, credentials):
    _message_mode(window, credentials, send_private_message, "private")


def _stream_message_mode(window, credentials):
    _message_mode(window, credentials, send_stream_message, "stream")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rcfile", help="Set rc file")
    args = parser.parse_args()
    credentials_file = args.rcfile if args.rcfile is not None \
        else "~/.tuplerrc"
    credentials = _get_credentials(credentials_file)
    stdscr = curses.initscr()
    _initialize_colors()
    stdscr.idlok(True)
    stdscr.scrollok(True)
    stdscr.clear()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)

    previous_message = None
    for message in message_loop(credentials):
        if message == Events.end_of_messages:
            c = stdscr.getch()
            if c >= 0:
                if ord('q') == c:
                    break
                elif ord('p') == c:
                    _private_message_mode(stdscr, credentials)
                elif ord('s') == c:
                    _stream_message_mode(stdscr, credentials)
            sleep(1)
        else:
            _display_message(stdscr, message, previous_message)
            previous_message = message
            stdscr.refresh()

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
