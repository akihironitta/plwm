#
# modestatus.py -- display various status information in xmodewin
#
#    Copyright (C) 2000-2001  Peter Liljenberg <petli@ctrl-c.liu.se>
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

import modewindow, wmanager, moveresize, wmevents
from Xlib import X, Xatom

# Screen mixin, requires ModeWindow
class ModeStatus:
    def __screen_client_init__(self):
        self.modestatus_modes = [ModeText(self, '')]
        self.modestatus_message = modewindow.Message(.5, modewindow.CENTER)
        self.modewindow_add_message(self.modestatus_message)

    def modestatus_new(self, text = ''):
        """Creates and returns a new ModeText object.
        The object will be put on top of the display stack.
        TEXT is the initial message of the object, an empty string if omitted.
        """
        mt = ModeText(self, text)
        self.modestatus_modes.append(mt)
        self.modestatus_message.set_text(text)
        return mt

    def modestatus_set_default(self, text):
        """Set the default status message to TEXT.
        """
        self.modestatus_modes[0].set(text)

    ### Internal functions below

    def modestatus_update(self, modetext):
        """Internal function, called by MODETEXT when it has changed.
        """
        if modetext is self.modestatus_modes[-1]:
            self.modestatus_message.set_text(modetext.text)

    def modestatus_remove(self, modetext):
        """Internal function, called by MODETEXT when it is popped.
        """
        try:
            self.modestatus_modes.remove(modetext)
        except ValueError:
            pass
        self.modestatus_message.set_text(self.modestatus_modes[-1].text)

class ModeText:
    """Class representing a mode status message.
    Don't instantiate it directly, use the modestatus_new()
    method of the screen instead.
    """

    def __init__(self, screen, text):
        self.screen = screen
        self.text = text

    def set(self, text):
        """Change the message to TEXT.
        """
        self.text = text
        self.screen.modestatus_update(self)

    def pop(self):
        """Remove this message from the display stack.
        """
        self.screen.modestatus_remove(self)

#
# Various mode functions
#

# Client mixin
class ModeFocusedTitleClient:
    def __client_init__(self):
        self.dispatch.add_handler(X.PropertyNotify, self.modefocusedtitle_property_notify)

    def modefocusedtitle_property_notify(self, event):
        if self.current and event.atom == Xatom.WM_NAME:
            self.screen.modestatus_set_default(self.get_title())

# Screen mixin
class ModeFocusedTitleScreen:
    def __screen_init__(self):
        self.dispatch.add_handler(wmevents.CurrentClientChange,
                                  self.modefocusedtitle_change)

    def modefocusedtitle_change(self, evt):
        if evt.client:
            # Reset modewindow on other screen
            if evt.screen and evt.screen != evt.client:
                evt.screen.modestatus_set_default('')

            # Set modewindow on this screen
            self.modestatus_set_default(evt.client.get_title())

        # Reset this modewindow
        else:
            self.modestatus_set_default('')


# Screen mixin
class ModeMoveResize:
    def __screen_init__(self):
        res = '.moveResize.modeFormat'
        cls = '.MoveResize.ModeFormat'
        default = '%(title)s [%(geometry)s]'
        self.modemoveresize_format = self.wm.rdb_get(res, cls, default)

        self.modemoveresize_text = None
        self.modemoveresize_tags = {}
        self.modemoveresize_hints = None
        self.dispatch.add_handler(moveresize.MoveResizeStart,
                                  self.modemoveresize_start)
        self.dispatch.add_handler(moveresize.MoveResizeDo,
                                  self.modemoveresize_do)
        self.dispatch.add_handler(moveresize.MoveResizeEnd,
                                  self.modemoveresize_end)
        self.dispatch.add_handler(moveresize.MoveResizeAbort,
                                  self.modemoveresize_end)

    def modemoveresize_start(self, ev):
        self.modemoveresize_tags['title'] = ev.client.get_title()
        self.modemoveresize_hints = ev.client.resize_increment() + ev.client.base_size()
        x, y, w, h = ev.client.geometry()[0:4]
        msg = self.modemoveresize_format_text(x, y, w, h)
        self.modemoveresize_text = self.modestatus_new(msg)

    def modemoveresize_do(self, ev):
        if self.modemoveresize_text:
            msg = self.modemoveresize_format_text(ev.x, ev.y, ev.width, ev.height)
            self.modemoveresize_text.set(msg)

    def modemoveresize_end(self, ev):
        if self.modemoveresize_text:
            self.modemoveresize_text.pop()
            self.modemoveresize_text = None
            self.modemoveresize_title = None
            self.modemoveresize_hints = None

    def modemoveresize_format_text(self, x, y, w, h):
        wi, hi, wb, hb = self.modemoveresize_hints
        if wi and wi > 1:
            w = (w - wb) / wi
        if hi and hi > 1:
            h = (h - hb) / hi
        self.modemoveresize_tags['geometry'] = '%dx%d+%d+%d' % (w, h, x, y)
        return self.modemoveresize_format % self.modemoveresize_tags
