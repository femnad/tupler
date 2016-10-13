import curses
import json
from os.path import expanduser
from time import sleep

from tupler_zulip_client import Credentials, Events, message_loop


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
    stdscr.nodelay(True)

    for message in message_loop(credentials):
        if message == Events.end_of_messages:
            c = stdscr.getch()
            if c >= 0 and ord('q') == c:
                break
            sleep(1)
        else:
            stdscr.addstr(message)
            stdscr.addstr('\n')
            stdscr.refresh()

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
