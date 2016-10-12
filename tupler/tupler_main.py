import curses
import json
from os.path import expanduser

from tupler_zulip_client import Credentials, message_loop


def _get_credentials(file_name):
    with open(expanduser(file_name)) as credentials_file:
        credentials = json.loads(credentials_file.read())
        return Credentials(**credentials)

if __name__ == "__main__":
    credentials = _get_credentials('~/.tuplerrc')
    stdscr = curses.initscr()
    stdscr.clear()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    for message in message_loop(credentials):
        stdscr.addstr(message)
        stdscr.addstr('\n')
        stdscr.refresh()

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
