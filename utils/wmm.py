#!/usr/bin/python
#
#    Copyright (C) 1999-2001  Peter Liljenberg <petli@ctrl-c.liu.se>
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


"""WMM, or Window Manager Manager, is a small X application which is
meant start window managers.

It could of course start most any application, but has a feature which
makes it suitable to debugging window managers: when mapped (e.g. if
iconified when the window manager crashes) it will raise itself to the
top of all other windows.  So even without a window manager, with
focus maybe locked on some unsuitable window, you can start a
fall-back window manager and clean up the situation.

WMM is configured with ~/.wmmrc.  For each non-blank line, not
starting with a #, WMM will create a button.  Each line should consist
of two tab-separated fields, the first is the button label and the
second is the command to run when the button is clicked.  If the second field is missing, WMM will instead quit when the button is clicked.
"""


import sys
import os

from Xlib import display, rdb, X, Xutil
import string


class Button:
    def __init__(self, parent, x, y, width, height, name):
        self.name = name
        self.window = parent.window.create_window(x, y, width, height, 1,
                                                  X.CopyFromParent, X.InputOutput,
                                                  X.CopyFromParent,
                                                  background_pixel = parent.background,
                                                  border_pixel = parent.foreground,
                                                  event_mask = (X.ExposureMask
                                                                | X.ButtonReleaseMask))

        self.gc = parent.gc
        self.width = width
        self.height = height

        # Center string
        ext = parent.font.query_text_extents(name)
        self.textwidth = ext.overall_width
        self.asc = ext.overall_ascent
        self.desc = ext.overall_descent

    def wantedwidth(self):
        return self.textwidth + 8

    def redraw(self):
        sx = max((self.width - self.textwidth) / 2, 3)
        sy = self.height / 2 + (self.asc + self.desc) / 2 - self.desc

        self.window.image_text(self.gc, sx, sy, self.name)

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.window.configure(width = width, height = height)
        self.window.clear_area(exposures = 1)

    def handle_event(self, event):
        if event.type == X.Expose:
            if event.count == 0:
                self.redraw()

        if event.type == X.ButtonRelease:
            self.button(event)

    def button(self, event):
        pass

class QuitButton(Button):
    def button(self, event):
        raise 'quit', 'quitting'

class CommandButton(Button):
    def __init__(self, parent, x, y, width, height, name, command):
        Button.__init__(self, parent, x, y, width, height, name)
        self.command = command

    def button(self, event):
        os.system(self.command)

class Main:
    def __init__(self, buttons, displayname = None):
        self.display = display.Display(displayname)
        self.screen = self.display.screen()

        self.foreground = self.screen.black_pixel
        self.background = self.screen.white_pixel

        font = '-*-lucida-medium-r-*-sans-12-*'
        self.font = self.display.open_font(font)
        if self.font is None:
            sys.stderr.write('%s: Failed to load font: %s\n'
                             % (sys.argv[0], font))
            self.font = self.display.open_font('fixed')

        fontsize = self.font.query()

        self.buttonheight = fontsize.font_ascent + fontsize.font_descent + 6

        height = len(buttons) * (self.buttonheight + 4) + 2
        width = 50

        root = self.screen.root
        self.window = root.create_window(100, 0, width, height, 1,
                                         X.CopyFromParent, X.InputOutput,
                                         X.CopyFromParent,
                                         background_pixel = self.background,
                                         border_pixel = self.foreground,
                                         event_mask = X.StructureNotifyMask)

        self.gc = self.window.create_gc(foreground = self.foreground,
                                        background = self.background,
                                        font = self.font)

        self.buttons = []
        x = 2
        y = 2
        w = width - 2 * x - 2
        h = self.buttonheight - 2

        for name, command in buttons:
            if command:
                self.buttons.append(CommandButton(self, x, y, w, h, name, command))
            else:
                self.buttons.append(QuitButton(self, x, y, w, h, name))
            y = y + h + 6

        self.buttonwidth = 0
        for b in self.buttons:
            if b.wantedwidth() > self.buttonwidth:
                self.buttonwidth = b.wantedwidth()

        self.window.configure(width = self.buttonwidth + 4, height = height)

        self.window.set_wm_hints(flags = (Xutil.InputHint | Xutil.StateHint),
                                 input = 1,
                                 initial_state = Xutil.NormalState)

        self.window.set_wm_normal_hints(flags = (Xutil.PMinSize | Xutil.PMaxSize),
                                        min_width = self.buttonwidth + 4,
                                        min_height = height,
                                        max_width = self.buttonwidth + 4,
                                        max_height = height)

        self.window.set_wm_name('WMManager')
        self.window.set_wm_class('wmm', 'WMManager')

        for b in self.buttons:
            b.resize(self.buttonwidth - 2, self.buttonheight)
            b.window.map()

        self.window.map()

    def loop(self):
        try:
            while 1:
                event = self.display.next_event()
                try:
                    win = event.window
                except AttributeError:
                    pass
                else:
                    if win == self.window:
                        self.handle_event(event)
                    else:
                        for b in self.buttons:
                            if win == b.window:
                                b.handle_event(event)
                                break
        except 'quit':
            self.window.destroy()
            sys.exit(0)

    def handle_event(self, event):
        if event.type == X.ConfigureNotify:
            self.buttonwidth = event.width - 4
            for b in self.buttons:
                b.resize(self.buttonwidth - 2, self.buttonheight)

        elif event.type == X.MapNotify:
            self.window.configure(stack_mode = X.Above)

        elif event.type == X.DestroyNotify:
            sys.exit(0)


def readrc():
    fn = os.path.join(os.environ['HOME'], '.wmmrc')
    try:
        lines = open(fn, 'r').readlines()
        buttons = []
        for line in lines:
            if line != '' and line[0] != '#':
                try:
                    label, comm = string.split(line, '\t', 1)
                    buttons.append((label, comm))
                except ValueError:
                    buttons.append((line, None))
        return buttons
    except IOError, msg:
        sys.stderr.write('%s: failed to read %s: %s\n'
                         % (sys.argv[0], fn, msg.strerror))
        return [('PLWM', 'plwm &'),
                ('TWM', 'twm &'),
                ('Quit', None)]

if __name__ == "__main__":
    m = Main(readrc())
    m.loop()

