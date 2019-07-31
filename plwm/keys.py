#
# keys.py -- Base keypress handlers
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

from Xlib import X, XK
from Xlib.keysymdef import latin1
import string
import wmanager
import event
import time
import sys

error = 'keys.error'

ReleaseModifier = X.AnyModifier << 1

modifiers = {
   's': X.ShiftMask,
   'S': X.ShiftMask,
   'c': X.ControlMask,
   'C': X.ControlMask,
   'm': X.Mod1Mask,
   'M': X.Mod1Mask,
   'M1': X.Mod1Mask,
   'M2': X.Mod2Mask,
   'M3': X.Mod3Mask,
   'M4': X.Mod4Mask,
   'M5': X.Mod5Mask,
   'Any': X.AnyModifier,
   'R': ReleaseModifier,
   'None': 0,
   }

def hash_keycode(code, modifiers):
    return modifiers << 8 | code;

# Screen mixin, still here for backward compitability
class KeyGrabber:
    """Keeps track of all grabbed keys on a window.
    """
    def __screen_init__(self):
        sys.stderr.write('%s: warning: Screen mixin KeyGrabber is deprecated, and will be removed in future releases.\n' % sys.argv[0])

# This is now the real grabbing class
class KeygrabManager:
    def __init__(self, wm, window):
        self.wm = wm
        self.window = window
        self.grabs = {}

    def ungrab_keys(self, keylist):
        """Ungrab some keys.

        KEYLIST is a list of (keycode, modifier) tuples.
        """
        for keycode, modifiers in keylist:
            h = hash_keycode(keycode, modifiers)
            c = self.grabs.get(h, 0)
            if c > 0:
                if c == 1:
                    del self.grabs[h]
                    self.window.ungrab_key(keycode, modifiers & ~ReleaseModifier)
                else:
                    self.grabs[h] = self.grabs[h] - 1

    def grab_keys(self, keylist):
        """Grab some keys.

        KEYLIST is a list of (keycode, modifier) tuples.
        """
        for keycode, modifiers in keylist:
            h = hash_keycode(keycode, modifiers)
            c = self.grabs.get(h, 0)
            if c == 0:
                self.window.grab_key(keycode, modifiers & ~ReleaseModifier, 1,
                                     X.GrabModeAsync, X.GrabModeAsync)
                self.grabs[h] = 1
            else:
                self.grabs[h] = self.grabs[h] + 1

    def grab_keyboard(self, time):
        s = self.window.grab_keyboard(0, X.GrabModeAsync, X.GrabModeAsync, time)
        if s != X.GrabSuccess:
            raise error, s

    def ungrab_keyboard(self):
        self.wm.display.ungrab_keyboard(X.CurrentTime)


class KeyHandler:
    """Class handling key events.

    Inherit this class and implement member methods for the various
    keysym.  The methods' names must have the following syntax:

    keymethod :== (modifier)* keysym
    modifier :== ('s' | 'c' | 'm') '_'

    The order of the modifiers are not importart, neither is their case.
        s means shift
        c means control
        m means meta (modifier 1)

    Examples:
        Return
        C_Right
        C_M_F1

    The methods must accept two arguments: the event object and the
    event handler group.

    Use a KeyHandler object as event handler for KeyPress and
    KeyRelease events.
    """

    propagate_keys = 1
    timeout = None

    def __init__(self, obj, deprecated_arg = None):
        """Instantiate a KeyHandler object.
        """

        # Warn if the deprecated and unused former "dispatch" argument
        # is used.
        if deprecated_arg is not None:
            sys.stderr.write("%s: warning: using deprecated KeyHandler __init__ interface\n" % sys.argv[0])


        wmanager.debug('mem', 'Initing keyhandler %s for %s', self, obj)

        # Figure out if we have been added to a WindowManager, Screen
        # or Client object.  Set up KeygrabManager objects if not
        # already done on screens or clients.

        if isinstance(obj, wmanager.WindowManager):
            wm = obj
            grabmgrs = []
            for s in obj.screens:
                if not hasattr(s, 'keygrab_mgr'):
                    s.keygrab_mgr = KeygrabManager(obj, s.root)
                grabmgrs.append(s.keygrab_mgr)

        elif isinstance(obj, wmanager.Screen):
            wm = obj.wm
            if not hasattr(obj, 'keygrab_mgr'):
                obj.keygrab_mgr = KeygrabManager(obj.wm, obj.root)
            grabmgrs = [obj.keygrab_mgr]

        elif isinstance(obj, wmanager.Window):
            wm = obj.wm
            if not hasattr(obj, 'keygrab_mgr'):
                obj.keygrab_mgr = KeygrabManager(obj.wm, obj.window)
            grabmgrs = [obj.keygrab_mgr]

        else:
            raise TypeError('expected WindowManager, Screen or Client object')


        # Dig through all names in this object, ignoring those beginning with
        # an underscore.

        # First collect all method names in this and it's base classes
        names = {}
        c = [self.__class__]
        while len(c):
            names.update(c[0].__dict__)
            c = c + list(c[0].__bases__)
            del c[0]

        names.update (self.__dict__)

        # And now parse the names
        rawbinds = []
        for name in names.keys():
            if name[0] != '_':

                # Find modifiers in name
                mask = 0
                parts = string.split(name, '_')
                while len(parts) >= 2 and modifiers.has_key(parts[0]):
                    mask = mask | modifiers[parts[0]]
                    del parts[0]

                # Find name keysym
                rest = string.join(parts, '_')
                keysym = XK.string_to_keysym(rest)
                if keysym != X.NoSymbol:
                    rawbinds.append((keysym, mask, getattr(self, name)))

        self.wm = wm
        self.dispatch = obj.dispatch
        self.grabmgrs = grabmgrs
        self.rawbindings = rawbinds
        self.grabs = []

        # Add handlers
        if self.propagate_keys:
            self.dispatch.add_handler(X.KeyPress, self._keyevent, handlerid = self)
            self.dispatch.add_handler(X.KeyRelease, self._keyevent, handlerid = self)
        else:
            self.dispatch.add_grab_handler(X.KeyPress, self._keyevent, handlerid = self)
            self.dispatch.add_grab_handler(X.KeyRelease, self._keyevent, handlerid = self)

        # Okay, so we will remap and regrab once for every
        # screen, but I'm not worried.  xmodmap isn't the most
        # frequently used command...
        self.dispatch.add_handler(X.MappingNotify, self._mappingnotify,
                                  handlerid = self)

        if self.timeout:
            self.last_key_time = None
            self.timer_id = event.new_event_type()
            self.timer = event.TimerEvent(self.timer_id, after = self.timeout)
            self.wm.events.add_timer(self.timer)
            self.dispatch.add_handler(self.timer_id, self._internal_timeout,
                                      handlerid = self)

        self._buildmap()

    def __del__(self):
        wmanager.debug('mem', 'Freeing keyhandler %s', self)
        self._cleanup()

    def _cleanup(self):
        # Remove all our event handlers
        self.dispatch.remove_handler(self)

        # Ungrab keys
        self._ungrab()

        # Clear the bindings: essential as elements of this list refers
        # to bound methods of this object, i.e. circular references.
        self.rawbindings = None
        self.bindings = None

        # Unscedule any pending timeout
        if self.timeout:
            self.timer.cancel()

    def _grab(self):
        for g in self.grabmgrs:
            g.grab_keys(self.grabs)

    def _ungrab(self):
        for g in self.grabmgrs:
            g.ungrab_keys(self.grabs)
        self.grabs = []

    def _buildmap(self):
        """Build key bindings mapping.

        Also sets passive grabs for the key bindings.
        """
        # First ungrab the grabs we already have
        self._ungrab()

        # Build up new list of bindings
        self.bindings = {}
        for keysym, modifiers, func in self.rawbindings:
            keycodes = self.wm.display.keysym_to_keycodes(keysym)
            for code, index in keycodes:
                # Don't deal with modeswitching, not yet
                if index > 1:
                    continue

                # If AnyModifier is set, we only grab to those keycodes which
                # have keysym as their primary binding
                if modifiers & X.AnyModifier:
                    if index != 0:
                        continue

                # Add shift if necessary
                if index == 1:
                    mods = modifiers | X.ShiftMask
                else:
                    mods = modifiers

                self.bindings[hash_keycode(code, mods)] = func
                self.grabs.append((code, mods))

        # Install the new grabs
        self._grab()

    def _mappingnotify(self, event):
        """Pass as handler for MappingNotify events to rebuild
        the key bindings.
        """
        self._buildmap()

    def _internal_timeout(self, ev):
        """Called when the timer event times out.
        Don't override this, override _timeout instead.
        """

        # Call _timeout if it has been at least self.timeout
        # seconds since the last keypress
        if self.last_key_time is None \
           or ev.time - self.last_key_time >= self.timeout:
            wmanager.debug('keys', 'timeout, last_key = %s, now = %s',
                           self.last_key_time, ev.time)
            self._timeout(ev)

        # If not: reschedule a timeout
        else:
            wmanager.debug('keys', 'rescheduling timeout at %s',
                           self.last_key_time + self.timeout)
            self.timer = event.TimerEvent(self.timer_id,
                                          at = self.last_key_time + self.timeout)
            self.wm.events.add_timer(self.timer)

    def _timeout(self, event):
        """Called when we really timeout.
        """
        pass

    def _keyevent(self, event):
        # Store key press time (approximate to the current time
        # as the X event.time isn't synced with that)
        self.last_key_time = time.time()

        wmanager.debug('keys', '%s %d %d, keyhandler %s',
                       event.__class__.__name__, event.detail, event.state, self)

        # Add in our release "modifier"
        if event.type == X.KeyRelease:
            extrastate = ReleaseModifier
        else:
            extrastate = 0

        # First check for an exact modifier match
        match = hash_keycode(event.detail, event.state | extrastate)
        if self.bindings.has_key(match):
            self.bindings[match](event)

        # else, check for an AnyModifier key
        else:
            match = hash_keycode(event.detail, X.AnyModifier | extrastate)
            if self.bindings.has_key(match):
                self.bindings[match](event)



class KeyGrabKeyboard(KeyHandler):
    propagate_keys = 0
    timeout = 10

    def __init__(self, obj, time, deprecated_arg = None):
        # Warn about using the old interface, and convert to new
        if deprecated_arg is not None:
            sys.stderr.write("%s: warning: using deprecated KeyGrabKeyboard.__init__ interface\n" % sys.argv[0])
            time = deprecated_arg

        self._grab_time = time
        KeyHandler.__init__(self, obj)

    def _grab(self):
        for g in self.grabmgrs:
            g.grab_keyboard(self._grab_time)

    def _ungrab(self):
        for g in self.grabmgrs:
            g.ungrab_keyboard()

    def _timeout(self, evt):
        self._cleanup()

def allmap(klass, method):
    """Map all printing keys to klass.method in keyhandler klass."""

    for c in dir(latin1):
        if len(c) > 3 and c[:3] == 'XK_':
            setattr(klass, c[3:], method)

