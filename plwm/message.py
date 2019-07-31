#
# message.py -- Screen mixin to messages.
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


"Message - a mixin to provide message on plwm screens."

import string
from types import StringType
from Xlib import X, Xutil
import event

class Message:
    "Holds and displays the message."

    def __init__(self, screen, fontname, draw_function,
                 foreground, background, bordercolor, borderwidth, seconds):
        "Initialize the message window, gc and font."

        self.wm = screen.wm
        self.seconds = seconds

        fg = screen.get_color(foreground)
        bg = screen.get_color(background)
        bc = screen.get_color(bordercolor)

        window = screen.root.create_window(0, 0, 1, 1, borderwidth,
                                           X.CopyFromParent, X.InputOutput,
                                           X.CopyFromParent,
                                           background_pixel = bg,
                                           border_pixel = bc,
                                           event_mask = (X.ExposureMask |
                                                         X.VisibilityChangeMask))

        self.font = self.wm.get_font(fontname, 'fixed')

        self.gc = window.create_gc(font = self.font, function = draw_function,
                                 foreground = fg, background = bg)
        self.window = screen.add_internal_window(window)
        self.window.dispatch.add_handler(X.VisibilityNotify, self.raisewindow)
        self.window.dispatch.add_handler(X.Expose, self.redraw)

    def setup(self, labels, align = 'left'):
        "Create the window."

        if type(labels) == StringType:
            labels = [labels]

        fontsize = self.font.query()
        high = (fontsize.font_ascent + fontsize.font_descent + 1)
        self.height = len(labels) * high

        self.line_height = high
        self.line_base_offset = fontsize.font_ascent + 1

        width = 0
        lines = []
        for l in range(len(labels)):
            line = Line(labels[l], self.font)
            w = line.width
            if w > width: width = w
            lines.append(line)
        self.width = width + 4

        for i in range(len(lines)):
            lines[i].setup(self.window.window, self.gc, self.width, align, i)
        self.lines = lines

        return self.width, self.height

    def display(self, x, y, timeout = None):
        "Start it up"

        x, y, width, height = self.window.keep_on_screen(x, y, self.width, self.height)
        self.window.configure(x = x, y = y, width = width, height = height)
        self.window.map()

        self.timeout = timeout or self.seconds * len(self.lines)

        if self.timeout:
            timer_id = event.new_event_type()
            self.timer = event.TimerEvent(timer_id, after = self.timeout)
            self.wm.events.add_timer(self.timer)
            self.wm.dispatch.add_handler(timer_id, self.close, handlerid = self)

    def hide(self):
        self.window.unmap()
        if self.timeout:
            self.timer.cancel()

    def close(self, event = None):
        self.hide()
        self.window.destroy()

    def raisewindow(self, event = None):
        self.window.raisewindow()

    def redraw(self, event = None):
        "Redraw the window, with highlights"

        self.window.clear_area(width = self.width, height = self.height)
        for i in range(len(self.lines)):
            self.lines[i].redraw(i * self.line_height + self.line_base_offset)


class Line:
    "A class for lines in a message."

    def __init__(self, label, font):
        "Figure out where to draw this string."

        self.name = label
        ext = font.query_text_extents(label)
        self.width = ext.overall_width

    def setup(self, window, gc, width, align, count):
        "Save the drawing position."

        self.window, self.gc = window, gc
        if align == 'left':
            self.x = 2
        elif align == 'center':
            self.x = (width - self.width) / 2
        else:        # right
            self.x = width - self.width - 2

    def redraw(self, y):
        "Draw myself."

        self.window.image_text(self.gc, self.x, y, self.name)

class screenMessage:
    """PLWM Screen mixin to provide messages..

    This mixin requires the color and font mixins be in the screen class."""

    message_font = "9x15Bold"
    message_foreground = "black"
    message_background = "white"
    message_bordercolor = "black"
    message_borderwidth = 3
    message_seconds = 5
    message_draw = X.GXset

    def message_make(self, labels, align = 'center'):
        """Create a message from the labels.

        Returns the width and height of the resulting menu."""

        self.message = Message(self, self.message_font, self.message_draw,
                             self.message_foreground, self.message_background,
                             self.message_bordercolor, self.message_borderwidth,
                             self.message_seconds)
        return self.message.setup(labels, align)

    def message_display(self, x, y):
        "Instantiate the menu, and return the label or None."

        self.message.display(x, y)
