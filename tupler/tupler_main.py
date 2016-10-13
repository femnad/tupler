import curses
import json
from os.path import expanduser
from time import sleep

from tupler_zulip_client import Credentials, Events, message_loop


def _get_credentials(file_name):
    with open(expanduser(file_name)) as credentials_file:
        credentials = json.loads(credentials_file.read())
        return Credentials(**credentials)


def _display_message(window, message):
    window.addstr("{}\n".format(message.sender), curses.color_pair(2))
    if not isinstance(message.recipient, list):  # Not a private message
        window.addstr(message.recipient, curses.color_pair(3))
        window.addstr(" > ")
        window.addstr(message.subject, curses.color_pair(4))
        window.addstr("\n")
    window.addstr("{}\n".format(message.content))


def _initialize_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_BLUE, -1)


if __name__ == "__main__":
    credentials = _get_credentials('~/.tuplerrc')
    stdscr = curses.initscr()
    _initialize_colors()
    stdscr.clear()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)

    for message in message_loop(credentials):
        if message == Events.end_of_messages:
            c = stdscr.getch()
            if c >= 0 and ord('q') == c:
                break
            sleep(1)
        else:
            _display_message(stdscr, message)
            stdscr.refresh()

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
