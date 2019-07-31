#
# menu.py -- Screen mixin to provide menus.
#
#    Copyright (C) 2001  Mike Meyer <mwm@mired.org>
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


"menu - a mixin to provide menus for plwm screens."

from Xlib import X
from keys import KeyGrabKeyboard, KeyHandler, allmap
from message import Message

class MenuKeyHandler(KeyGrabKeyboard):
    """Template for handling a menu.

    MenuKeyHandler defines the following event handler methods:

    _up, _down - move the cursor up or down the menu.

    _do - perform the currently selected menu action.
    _abort - exit the menu with no actions."""

    timeout = None

    def __init__(self, menu):
        KeyGrabKeyboard.__init__(self, menu.window, X.CurrentTime)
        self.menu = menu

    def _up(self, event): self.menu.up()
    def _down(self, event): self.menu.down()

    def _do(self, event):
        self._cleanup()
        self.menu.do()

    def _abort(self, event):
        self._cleanup()
        self.menu.close()


class MenuCharHandler(MenuKeyHandler):
    """MenuCharHandler allows "one-key access" to menu entries.

    This adds the _goto method, which goes to the first menu label
    that starts with a character >= the event keycode, then the latin1
    symbols to that method."""

    def _goto(self, event):
        char = chr(self.wm.display.keycode_to_keysym(event.detail, 0))
        if event.state:
            char = char.upper()
        return self.menu.goto(char)
allmap(MenuCharHandler, MenuCharHandler._goto)


class MenuCharSelecter(MenuCharHandler):
    """A MenuCharHandler with intanst selection.

    Just like MenuCharHandler, except when you hit the character,
    it not only takes you there, it issues the command if the character
    is in the menu. Otherwise, it acts like MenuCharHandler."""

    def _goto(self, event):
        if MenuCharHandler._goto(self, event):
            self._do(event)
allmap(MenuCharSelecter, MenuCharSelecter._goto)

class Menu(Message):
    "Holds and manipulates the menu."

    def setup(self, labels, align = 'center'):
        "Initialize the menu window, gc and font"

        width, height = Message.setup(self, labels, align)
        self.high = height / len(self.lines)
        self.current = 0
        return width, height

    def start(self, x, y, action, handler, timeout = 0):
        """Start it up...

           Passing x,y = -1,-1 will cause the menu to be centred on the
           screen.
        """

        if x==-1 and y==-1:
            x = self.wm.current_screen.root_x + \
                self.wm.current_screen.root_width/2-self.width/2
            y = self.wm.current_screen.root_y + \
                self.wm.current_screen.root_height/2-self.height/2

        Message.display(self, x, y, timeout)
        self.window.get_focus(X.CurrentTime)
        self.action = action
        handler(self)

    def up(self):
        "Move the menu selection up."

        self.current = self.current - 1
        if self.current < 0: self.current = len(self.lines) - 1
        self.redraw()

    def down(self):
        "Move the menu selection down"

        self.current = self.current + 1
        if self.current >= len(self.lines): self.current = 0
        self.redraw()

    def goto(self, char):
        """Goto the first entry with a label that starts >= char

        returns true if entry actually starts with char."""

        length = len(self.lines)
        lc = char.lower()
        for i in range(length):
            if (lc, char) <= (self.lines[i].name[0].lower(), self.lines[i].name[0]):
                break
        if i < length: self.current = i
        else: self.current = length - 1
        self.redraw()
        return char == self.lines[i].name[0]

    def do(self):
        "Run it!"

        self.close()
        self.wm.display.sync()
        self.action(self.lines[self.current].name)

    def redraw(self, event = None):
        "Redraw the window, with highlights"

        Message.redraw(self)
        self.window.fill_rectangle(self.gc, 0, self.current * self.high,
                                        self.width, self.high)


class screenMenu:
    """PLWM Screen mixin to provide a per-screen menu.

    This mixin requires the color and font mixins be in the screen class."""

    menu_font = "9x15Bold"
    menu_foreground = "black"
    menu_background = "white"
    menu_bordercolor = "black"
    menu_borderwidth = 3
    menu_seconds = 0
    menu_draw = X.GXinvert

    def menu_make(self, labels, align = 'center'):
        """Create a menu of labels.

        Returns the width and height of the resulting menu."""

        self.menu = Menu(self, self.menu_font, self.menu_draw,
                             self.menu_foreground, self.menu_background,
                             self.menu_bordercolor, self.menu_borderwidth,
                             self.menu_seconds)
        return self.menu.setup(labels, align)

    def menu_run(self, x, y, action):
        "Instantiate the menu, and return the label or None."

        self.menu.start(x, y, action, self.menu_handler)
