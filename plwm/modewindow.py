#
# modewindow.py -- manage a mode window within PLWM
#
#    Copyright (C) 2001  Peter Liljenberg <petli@ctrl-c.liu.se>
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


from Xlib import X
import wmanager

TOP = 0
BOTTOM = 1

LEFT = 0
CENTER = 1
RIGHT = 2

# Screen mixin
class ModeWindowScreen:
    modewindow_pos = TOP

    def __screen_client_init__(self):
        fg = self.get_color_res('.modewindow.foreground',
                                '.ModeWindow.Foreground',
                                '#ffffff')

        bg = self.get_color_res('.modewindow.background',
                                '.ModeWindow.Background',
                                '#000000')

        self.modewindow_mw = ModeWindow(self, fg, bg,
                                        self.wm.get_font_res('.modewindow.font',
                                                             '.ModeWindow.Font',
                                                             'fixed'),
                                        self.modewindow_pos)


    def modewindow_add_message(self, message):
        self.modewindow_mw.add_message(message)

    def modewindow_remove_message(self, message):
        self.modewindow_mw.remove_message(message)

class ModeWindow:
    def __init__(self, screen, fg, bg, font, pos):
        self.messages = []

        fq = font.query()

        font_center = (fq.font_ascent + fq.font_descent) / 2 - fq.font_descent
        height = fq.font_ascent + fq.font_descent + 6

        if pos == TOP:
            c = screen.alloc_border('top', height)
        else:
            c = screen.alloc_border('bottom', height)

        self.x, self.y, self.width, self.height = c

        self.base = self.height / 2 + font_center

        window = screen.root.create_window(
            self.x, self.y, self.width, self.height, 0,
            X.CopyFromParent, X.InputOutput, X.CopyFromParent,
            background_pixel = bg,
            event_mask = X.ExposureMask
            )

        self.gc = window.create_gc(foreground = fg, font = font)

        self.window = screen.add_internal_window(window)
        self.window.dispatch.add_handler(X.Expose, self.redraw)
        window.map()


    def add_message(self, message):
        try:
            self.messages.index(message)
        except ValueError:
            self.messages.append(message)
            message.add_to_mw(self)

    def remove_message(self, message):
        try:
            message.remove_from_mw(self)
            self.messages.remove(message)
        except ValueError:
            pass

    def redraw(self, event):
        for m in self.messages:
            m.draw(self)


class Message:
    def __init__(self, position, justification = CENTER, nice = 0, text = None):
        if position < 0 or position > 1:
           raise ValueError('position should be in the interval [0.0, 1.0], was %s'
                            % position)

        self.position = position
        self.justification = justification
        self.nice = nice
        self.text = text
        # Mapping of modewins to text widths
        self.modewins = {}

    def add_to_mw(self, mw):
        self.modewins[mw] = None
        self.draw(mw)

    def remove_from_mw(self, mw):
        self.undraw(mw)
        del self.modewins[mw]

    def set_text(self, text):
        if text == self.text:
            return

        self.text = text

        for mw in self.modewins.keys():
            self.undraw(mw)
            self.modewins[mw] = None
            self.draw(mw)

    def draw(self, mw):
        if not self.text:
            return

        pos = self.modewins[mw]

        if pos is None:
            # Get width
            if self.text:
                f = mw.gc.query_text_extents(self.text)
                width = f.overall_width + 4
            else:
                width = 0

            # Get x pos
            x = (mw.width * self.position)

            if self.justification == CENTER:
                x = x - width / 2

            elif self.justification == RIGHT:
                x = x - width

            self.modewins[mw] = (width, x)

        else:
            width, x = pos

        mw.window.draw_text(mw.gc, x + 2, mw.base, self.text)

    def undraw(self, mw):
        pos = self.modewins[mw]

        if pos is not None:
            width, x = pos
            mw.window.clear_area(x = x, width = width)

