#
# input.py -- input editing for PLWM
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


"input - a tool for getting input from the user."

from Xlib import X, Xatom
from keys import KeyGrabKeyboard, allmap
from wmanager import Window

class InputKeyHandler(KeyGrabKeyboard):
    """Template for handling user input.

    InputKeyHandler defines the following event handler methods:

    _insert - insert the character typed. The latin1 character set is
            bound to this by default.

    _forw, _back - move the cursor forward or backward in the input

    _delforw, _delback - delete the character forward or backward in the input

    _end, _begin - move the cursor to the end or beginning of the input

    _deltoend - remove all characters to the end of the input

    _paste - paste the current selection into the intput. The handler
             must be an instance of wmanager.Window for this to work

    _done - run action on the current string

    _abort - exit without doing anything

    _history_up - scroll to newer events

    _history_down - scroll to older events"""

    timeout = None

    def __init__(self, handler, display, history):
        """Init with a handler and display.

        handler is a handler object appropriate for KeyGrabKeyboard.
        display has show(left, right), do(string) and abort() methods.
            both abort() and do() should clean up the object.
        history is a list of strings we let the user scroll through."""

        KeyGrabKeyboard.__init__(self, handler, X.CurrentTime)
        self.display = display
        self.handler = handler
        self.history = history
        self.history_index = len(history)
        self.left = ""
        self.right = ""
        if isinstance(handler, Window):
            self.selection = self.wm.display.intern_atom("SELECTION")
            self.wm.dispatch.add_handler(X.SelectionNotify,
                                       self._paste_selection, handlerid = self)
        display.show(self.left, self.right)

    def _paste_selection(self, event):
        if event.property:
            sel = self.handler.window.get_full_property(self.selection, Xatom.STRING)
            if sel and sel.format == 8:
                self.left = self.left + sel.value
                self.display.show(self.left, self.right)

    def _paste(self, event):
        if isinstance(self.handler, Window):
            self.handler.window.convert_selection(Xatom.PRIMARY, Xatom.STRING,
                                                self.selection, X.CurrentTime)

    def _insert(self, event):
        if event.type != X.KeyPress: return
        sym = self.wm.display.keycode_to_keysym(event.detail,
                                                event.state & X.ShiftMask != 0)
        chr = self.wm.display.lookup_string(sym)
        if chr: self.left = self.left + chr
        self.display.show(self.left, self.right)

    def _forw(self, event):
        if self.right:
            self.left = self.left + self.right[0]
            self.right = self.right[1:]
        self.display.show(self.left, self.right)

    def _back(self, event):
        if self.left:
            self.right = self.left[-1] + self.right
            self.left = self.left[:-1]
        self.display.show(self.left, self.right)

    def _delforw(self, event):
        if self.right:
            self.right = self.right[1:]
        self.display.show(self.left, self.right)

    def _delback(self, event):
        if self.left:
            self.left = self.left[:-1]
        self.display.show(self.left, self.right)

    def _deltoend(self, event):
        self.right = ""
        self.display.show(self.left, self.right)

    def _end(self, event):
        self.left = self.left + self.right
        self.right = ""
        self.display.show(self.left, self.right)

    def _begin(self, event):
        self.right = self.left + self.right
        self.left = ""
        self.display.show(self.left, self.right)

    def _done(self, event):
        res = self.left + self.right
        self.history.append(res)
        self.display.do(res)
        self.wm.dispatch.remove_handler(self)
        self._cleanup()

    def _abort(self, event):
        self.display.abort()
        self.wm.dispatch.remove_handler(self)
        self._cleanup()

    def _history_up(self, event):
        if len(self.history):
            if self.history_index > 0:
                self.history_index -= 1
                self.left = self.history[self.history_index]
                self.right = ""
                self.display.show(self.left, self.right)

    def _history_down(self, event):
        if len(self.history):
            if self.history_index <(len(self.history)-1):
                self.history_index += 1
                self.left = self.history[self.history_index]
                self.right = ""
                self.display.show(self.left, self.right)

allmap(InputKeyHandler, InputKeyHandler._insert)

class inputWindow:
    "Class to get a line of user input in a window."

    fontname= "9x15"
    foreground = "black"
    background = "white"
    borderwidth = 3
    bordercolor = "black"
    history = []

    def __init__(self, prompt, screen, length=30):

        if not prompt: prompt = ' '        # We have problems if there's no prompt, so add one.
        self.string = self.prompt = prompt
        self.offset = len(self.prompt)
        self.length = length + self.offset
        self.start = 0
        fg = screen.get_color(self.foreground)
        bg = screen.get_color(self.background)
        bc = screen.get_color(self.bordercolor)
        font = screen.wm.get_font(self.fontname, 'fixed')
        size = font.query()
        self.height = size.font_ascent + size.font_descent + 1
        self.width = font.query_text_extents(prompt).overall_width + \
                   font.query_text_extents(length * 'm').overall_width
        self.baseline = size.font_ascent + 1

        window = screen.root.create_window(0, 0, self.width, self.height,
                                           self.borderwidth,
                                           X.CopyFromParent, X.InputOutput,
                                           X.CopyFromParent,
                                           background_pixel = bg,
                                           border_pixel = bc,
                                           event_mask = (X.VisibilityChangeMask |
                                                         X.ExposureMask))

        self.gc = window.create_gc(font = font, function = X.GXinvert,
                                 foreground = fg, background = bg)

        self.font = font
        self.window = screen.add_internal_window(window)
        self.window.dispatch.add_handler(X.VisibilityNotify, self.raisewindow)
        self.window.dispatch.add_handler(X.Expose, self.redraw)

    def read(self, action, handlertype, x=0, y=0):
        "Open the window at x, y, using handlertype, and doing action."

        self.action = action
        x, y, width, height = self.window.keep_on_screen(x, y, self.width, self.height)
        self.window.configure(x = x, y = y, width = width, height = height)
        self.window.map()
        self.window.get_focus(X.CurrentTime)
        handlertype(self.window, self, self.history)

    def raisewindow(self, event):
        self.window.raisewindow()

    def redraw(self, event = None):
        length = len(self.string)

        if self.offset < length:
            wide = self.font.query_text_extents(self.string[self.offset]).overall_width
        else:
            wide = self.font.query_text_extents(' ').overall_width

        if self.start >= self.offset: self.start = self.offset - 1
        left = self.font.query_text_extents(self.string[self.start:self.offset]).overall_width

        if left + wide >= self.width:
            self.start = self.offset - self.length + 1
            left = self.font.query_text_extents(self.string[self.start:self.offset]).overall_width

        self.window.clear_area(width = self.width, height = self.height)
        self.window.image_text(self.gc, 0, self.baseline, self.string[self.start:])
        self.window.fill_rectangle(self.gc, left, 0, wide, self.height)


    def show(self, left, right):
        if left:
            self.string = self.prompt + left
        else:        # Display the prompt in this case.
            self.string = self.prompt
            self.start = 0
        self.offset = len(self.string)
        self.string = self.string + right
        self.redraw()

    def do(self, string):
        self.action(string)
        self.window.destroy()

    def abort(self):
        self.window.destroy()


class modeInput:
    "Class to get input via the modewindow."

    history = []

    def __init__(self, prompt, screen, length = None):
        # ignore length argument
        self.prompt = prompt
        self.screen = screen

    def read(self, action, handlertype, x = 0, y = 0):
        self.action = action
        self.status_msg = self.screen.modestatus_new(self.prompt + "_")
        handlertype(self.screen.modewindow_mw.window, self, self.history)

    def show(self, left, right):
        self.status_msg.set("%s%s_%s" % (self.prompt, left, right))

    def do(self, string):
        self.action(string)
        self.status_msg.pop()

    def abort(self):
        self.status_msg.pop()


