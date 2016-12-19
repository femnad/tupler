import argparse
import curses
from curses.textpad import Textbox, rectangle
from curses import wrapper
from enum import Enum
from functools import partial
import json
from os.path import expanduser
from time import sleep

from tupler.tupler_zulip_client import (
    Events, get_credentials, get_unread_messages, message_loop,
    send_private_message, send_stream_message
)


class MessageType(Enum):
    private = 1
    stream = 2


def _get_credentials(file_name):
    with open(expanduser(file_name)) as credentials_file:
        credentials = json.loads(credentials_file.read())
        return get_credentials(**credentials)


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


help_text = {MessageType.private: 'recipient and message',
             MessageType.stream: 'stream, subject and message'}


def _message_mode(window, credentials, message_function, message_type):
    window.clear()
    window.nodelay(False)
    message_help_text = help_text[message_type]
    window.addstr(0, 0,
                  "Enter {} for {} message, Ctrl-G to switch/submit".format(
                      message_help_text, message_type.name))
    boxes = []
    recipient_win = curses.newwin(1, 50, 2, 1)
    rectangle(window, 1, 0, 3, 52)
    recipient_box = Textbox(recipient_win)
    boxes.append(recipient_box)

    subject_box = None
    if message_type == MessageType.stream:
        subject_win = curses.newwin(1, 50, 2, 54)
        rectangle(window, 1, 53, 3, 104)
        subject_box = Textbox(subject_win)
        boxes.append(subject_box)

    content_win = curses.newwin(5, 103, 5, 1)
    rectangle(window, 4, 0, 10, 104)
    content_box = Textbox(content_win)
    boxes.append(content_box)
    window.refresh()

    recipient_box.edit()
    if message_type == MessageType.stream:
        subject_box.edit()
    content_box.edit()
    components = [box.gather().strip() for box in boxes]
    message_function(credentials, *components)

    window.clear()
    window.refresh()
    window.nodelay(True)


def _private_message_mode(window, credentials):
    _message_mode(window, credentials, send_private_message,
                  MessageType.private)


def _stream_message_mode(window, credentials):
    _message_mode(window, credentials, send_stream_message, MessageType.stream)


keybindings = {'p': _private_message_mode, 's': _stream_message_mode}


def _main(stdscr):
    parser = argparse.ArgumentParser()
    parser.add_argument("--rcfile", help="Set rc file")
    args = parser.parse_args()
    credentials_file = args.rcfile if args.rcfile is not None \
        else "~/.tuplerrc"
    credentials = _get_credentials(credentials_file)
    _initialize_colors()
    stdscr.idlok(True)
    stdscr.scrollok(True)
    stdscr.clear()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)

    unread_messages = get_unread_messages(credentials)
    for unread_message in unread_messages:
        _display_message(stdscr, unread_message)

    previous_message = None
    for message in message_loop(credentials):
        if message == Events.end_of_messages:
            c = stdscr.getch()
            if c >= 0:
                key = chr(c)
                if key == 'q':
                    break
                else:
                    action = keybindings.get(key)
                    if action is not None:
                        action(stdscr, credentials)
            sleep(1)
        else:
            _display_message(stdscr, message, previous_message)
            previous_message = message
            stdscr.refresh()

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()


def main():
    wrapper(_main)
