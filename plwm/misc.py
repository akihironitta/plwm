#
# misc.py -- various small mixins and other functions
#
#    Copyright (C) 2002  Peter Liljenberg <petli@ctrl-c.liu.se>
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

from Xlib import X, XK, Xatom

import wmanager
import keys

class InitialKeepOnScreenClient:

    """This Client mixin will make sure that new windows is entirely
    visible on the screen.  If necessary, they will be moved and
    resized to fit on the screen.

    Put this mixin after any mixin that might change the window size
    or the border width.
    """

    def __client_init__(self):
        x, y, w, h = self.keep_on_screen(self.x, self.y,
                                         self.width, self.height)
        w, h = self.follow_size_hints(w, h)
        self.configure(x = x, y = y, width = w, height = h)




class MozillaPopupKeymap(keys.KeyHandler):
    """Keymap for the InhibitMozillaPopups mixin.

    Subclass it to define your own accept key, e.g.:

    class MyMozillaPopupKeymap(misc.MozillaPopupKeymap):
            M5_a = misc.MozillaPopupKeymap._accept
        _key_name = 'M5-a'
    """

    timeout = 5
    _key_name = 'special key'

    def __init__(self, client):
        keys.KeyHandler.__init__(self, client.wm)
        self.client = client
        self.status_msg = self.wm.current_screen.modestatus_new('Mozilla popup detected, press %s to accept' % self._key_name)

    def _accept(self, ev):
        wmanager.debug('mozilla', 'Accepting popup')
        self.status_msg.pop()
        # Deiconify-by-moving-back...
        # self.client.moveresize(0, 20, self.client.width, self.client.height, 1)
        self.client.deiconify()
        self._cleanup()

    def _timeout(self, ev):
        wmanager.debug('mozilla', 'Rejecting popup')
        self.status_msg.pop()

        # Delete the window, unless the user already has deiconified it
        if not self.client.is_mapped():
            self.client.delete(1)

        self._cleanup()


# client mixin
class InhibitMozillaPopups:

    """This client mixin will detect popup-windows from Netscape 6.1,
    and possibly other Mozilla versions.

    They will not be allowed to be displayed unless the user press a
    certain key within five seconds.

    You must define the client attribute mozpopup_keymap to the
    subclass of InhibitMozillaKeymap to use as popup keymap.
    """

    mozpopup_keymap = None

    def __client_init__(self):
        assert self.mozpopup_keymap is not None

        # Recognize Netscape 6.1 popups in this manner:
        # They have class Mozilla-bin.
        # They are not WM_TRANSIENT_FOR windows.
        # They have _MOTIF_WM_HINTS set, where MwmHints.flags have
        # MWM_HINTS_DECORATIONS set,
        # and MwmHints.decorations not in (MWM_DECOR_ALL, 0x7e)
        # (struct and flags defined in MwmUtil.h)

        # Only act when the window was found thanks to a maprequest.
        if not self.from_maprequest:
            return

        if self.res_class != 'Mozilla-bin':
            return

        MWM_HINTS = self.wm.display.intern_atom("_MOTIF_WM_HINTS")
        WM_TRANSIENT_FOR = self.wm.display.intern_atom("WM_TRANSIENT_FOR")

        r = self.window.get_property(WM_TRANSIENT_FOR, Xatom.WINDOW, 0, 1)
        if r is not None:
            return

        r = self.window.get_property(MWM_HINTS, MWM_HINTS, 0, 5)
        if r is None or r.format != 32 or len(r.value) != 5:
            return

        # Check flags and decoration
        if r.value[0] & 2 and r.value[2] not in (1, 0x7edd):
            wmanager.debug('mozilla', 'detected mozilla popup')

            # Don't map window immediately, and install
            # a temporary keymap to allow activating the window
            self.start_iconified = 1
            self.mozpopup_keymap(self)
            self.wm.display.bell(0)


# keymap
class RunKeys(keys.KeyGrabKeyboard):

    """This keymap uses the modewindow to allow the user to enter a
    command to be run.  Start it in a key handler method from your
    ordinary keymap, e.g.:

    def M5_e(self, evt):
        misc.RunKeys(self, evt)

    The prompt is indicated with an underscore, but editing is limited
    to deleting the last character.

    The command entered will be executed in the background when return
    is pressed.  Escape aborts.
    """

    propagate_keys = 0
    timeout = 0

    def __init__(self, keyhandler, evt):
        keys.KeyGrabKeyboard.__init__(self, keyhandler.wm, evt.time)
        self.run_cmd = ''
        self.status_msg = self.wm.current_screen.modestatus_new('Enter command: _')

    def _keyevent(self, event):
        if event.type != X.KeyPress:
            return

        sym = self.wm.display.keycode_to_keysym(event.detail,
                                                event.state & X.ShiftMask != 0)
        if not sym:
            return

        if sym == XK.XK_Return:
            if self.run_cmd:
                self.wm.system(self.run_cmd)
            self.status_msg.pop()
            self._cleanup()
            return

        if sym == XK.XK_Escape:
            self.status_msg.pop()
            self._cleanup()
            return

        if sym in (XK.XK_BackSpace, XK.XK_Delete):
            self.run_cmd = self.run_cmd[:-1]
        else:
            chr = self.wm.display.lookup_string(sym)
            if chr:
                self.run_cmd = self.run_cmd + chr

        self.status_msg.set('Enter command: %s_' % self.run_cmd)
