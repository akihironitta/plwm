#!/usr/bin/env python
#
# pane_utilities.py -- Utility clases and functions for use with panes
#
#    Copyright (C) 2005  Mike Meyer <mwm@mired.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from os import environ
import cfilter, string
from webbrowser import open_new
from urllib import quote

class appmenu:
    "Creates a menu of applications to run in a pane."

    def __init__(self, pane, apps):
        "Create and run the applications menu from the keys."

        labels = apps.keys()
        labels.sort(key=lambda x: (x[0].lower(), x))
        width, height = pane.screen.menu_make(labels)
        self.system = pane.screen.system
        self.apps = apps
        pane.screen.menu_run((pane.width - width) / 2 + pane.x,
                         (pane.height - height) / 2 + pane.y,
                         self)

    def __call__(self, choice):
        "Call the system function on the value of the given choice."

        self.system(self.apps[choice] + " &")


class codemenu:
    "Create a menu of Python actions to run."

    def __init__(self, pane, actions=None):
        "Create the menu and run it."

        if actions:
            self.actions = actions
        else:
            self._make(pane)
        labels = self.actions.keys()
        labels.sort(key=lambda c: (c[0].lower(), c))
        width, height = pane.screen.menu_make(labels, align="left")
        pane.screen.menu_run((pane.width - width) / 2 + pane.x,
                         (pane.height - height) / 2 + pane.y,
                         self)

    def __call__(self, choice):
        "Run the selection for the user."

        apply(apply, self.actions[choice])

    def _make(self, pane):
        """Make a dictionary from my methods and docstrings:

        For all method names that are one character long, the key will
        be the method name, a ': ', then the first word of the docstring. The value
        will be a the method."""

        self.actions = dict()
        for name in dir(self):
            if len(name) == 1:
                meth = getattr(self, name)
                name = '%s: %s' % (name, meth.__doc__)
                self.actions[name] = meth, (pane,)

class view_menu(codemenu):
    "The view for use when actions is an MVC controller."

    def __call__(self, choice):
        self.actions.choose(choice)


class windowmenu:
    "Create a menu of windows to add to a pane."

    def __init__(self, pane, filter = cfilter.true, startlist = None):
        labels = []
        clients = {}
        clientlist = startlist or pane.screen.query_clients(filter, 1)
        clientlist.sort(key=lambda c: (c.get_title()[0].lower(), c.get_title()))
        i = 'a'
        # We really need to deal with window lists longer than 26.
        for c in clientlist:
            l = "%c: %s" % (i, c.get_title())
            labels.append(l)
            clients[l] = c
            i = chr(ord(i) + 1)
        if labels:
            width, height = pane.screen.menu_make(labels, align = 'left')
            self.add = pane.add_window
            self.clients = clients
            pane.screen.menu_run((pane.width - width) / 2 + pane.x,
                                 (pane.height - height) / 2 + pane.y,
                                 self)
        else:
            width, height = pane.screen.message_make("No windows")
            pane.screen.message_display((pane.width - width) / 2 + pane.x,
                                        (pane.height - height) / 2 + pane.y)

    def __call__(self, choice):
        "Add the selected window to the pane."

        self.add(self.clients[choice])


class panesmenu:
    "Create a menu of all the panes."

    def __init__(self, screen):
        wm = screen.wm
        labels = []
        panes = {}
        for i in range(len(wm.panes_list)):
            w = wm.panes_list[i].window
            if w: l = "%d: %s" % (i, w.get_title())
            else: l = "%d: <EMPTY>" % i
            labels.append(l)
            panes[l] = i
        width, height = screen.menu_make(labels, align = 'left')
        self.goto = wm.panes_goto
        self.panes = panes
        screen.menu_run(screen.root_x + (screen.root_width - width) / 2,
                        screen.root_y + (screen.root_height - height) / 2, self)

    def __call__(self, choice):
        "Activate the selected pane."

        self.goto(self.panes[choice])


class websearch:
    "Launch a browser with a web search from the user."

    def __init__(self, pane, name, winclass, format, browser = None):
        self.format = format
        self.browser = browser
        self.pane = pane
        window = winclass("Search %s: " % name, pane.screen, length=50)
        window.read(self, window.editHandler, pane.x, pane.y)

    def __call__(self, string):
        query = self.format % quote(string)
        if self.browser:
            self.browser(query)
        else:
            environ['DISPLAY'] = self.pane.screen.displaystring
            open_new(query)


class runcommand:
    "Read a string from the user, and run it."

    def __init__(self, pane, winclass, prompt = "Command: "):
        self.system = pane.screen.system
        window = winclass(prompt, pane.screen, length = 50)
        window.read(self, window.editHandler, pane.x, pane.y)

    def __call__(self, string):
        self.system(string + " &")


class splitpane:
    "Read in a fraction, and split that much off the current pane."

    def __init__(self, pane, splitter, winclass, prompt = "Fraction: "):
        self.pane, self.splitter = pane, splitter
        window = winclass(prompt, pane.screen, length = 50)
        window.read(self, window.editHandler, pane.x, pane.y)

    def __call__(self, fraction):
        try:
            f = string.atof(fraction)
            self.splitter(f)
        except ValueError:
            pass


class numberpane:
    "Read a new number for the current pane."

    def __init__(self, pane, winclass, prompt = "New number: "):
        self.wm = pane.wm
        window = winclass(prompt, pane.screen)
        window.read(self, window.editHandler, pane.x, pane.y)

    def __call__(self, name):
        self.wm.panes_number(int(name))


class pullwindow:
    "Read a window's name, and pull it to the current pane."

    def __init__(self, pane, winclass, prompt = "Pull: "):
        self.pane = pane
        window = winclass(prompt, pane.screen)
        window.read(self, window.editHandler, pane.x, pane.y)

    def __call__(self, name):
        clients = self.pane.screen.query_clients(cfilter.re_title(name + ".*"), 1)
        if len(clients) == 1: self.pane.add_window(clients[0])
        elif clients: windowmenu(self.pane, startlist = clients)
        else:
            width, height = self.pane.screen.message_make("No windows")
            self.pane.screen.message_display(self.pane.x, self.pane.y)


class gotowindow:
    "Emulate the rp 'goto' command."

    def __init__(self, pane, winclass, prompt = "Goto: "):
        self.pane = pane
        window = winclass(prompt, pane.screen)
        window.read(self, window.editHandler)

    def __call__(self, name):
        clients = self.pane.screen.query_clients(cfilter.re_title(name + ".*"), 1)
        if clients:
            window = clients[0]
            if window.panes_pane.window and window.panes_pane.window == window:
                self.pane.wm.panes_activate(window.panes_pane)
            else:
                self.pane.add_window(window)
        else:
            width, height = self.pane.screen.message_make("No windows")
            self.pane.screen.message_display(0, 0)


def split_pane(count, splitter):
    """Invoke a pane splitter to divide a pane up into count pieces."""

    while count > 1:
        splitter(1. / count)
        count -= 1


def getapp(pane, name, command = None):
    "Find a window starting with name, and run command if it doesn't exist."

    clients = pane.screen.query_clients(cfilter.re_title(".*%s.*" % name), 1)
    if len(clients) > 1: windowmenu(pane, startlist = clients)
    elif clients: pane.add_window(clients[0])
    else: pane.screen.system((command or name) + " &")


