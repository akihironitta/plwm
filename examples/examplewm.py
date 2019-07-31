#!/usr/bin/env python
#
# petliwm.py -- Example PLWM window manager "configuration"
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

"""Example PLWM window manager

This example demonstrates basic window manager construction and some of the
more common window manager concepts such as a mode window, multiple views,
and window decorations.

"""
import sys
import os

# Allow running from examples dir in source tree
if os.path.exists(os.path.join(sys.path[0], '../plwm/__init__.py')):
    sys.path[1:1] = [os.path.join(sys.path[0], '..')]

import time

from Xlib import X

from plwm import wmanager, focus, keys, \
     deltamove, outline, \
     frame, color, font, views, \
     modewindow, modestatus, \
     mw_clock, mw_biff, \
     inspect

from plwm.cycle import CycleKeys
from plwm.moveresize import MoveResizeKeys

import plwm.filters as f
import plwm.cfilter as cf

delta = deltamove.DeltaMove()

class MyClient(wmanager.Client,
               outline.XorOutlineClient,
               modestatus.ModeFocusedTitleClient):
    """Example client class

    This class adds an XOR outline for moving/resizing windows and a hook to
    display the title of the currently-focused window in the mode window. It
    also specifies a list of clients that should start in an iconified
    (withdrawn) state and specifies default pointer positions for a couple of
    programs.

    """
    # Put a frame around all client windows
    window_proxy_class = frame.FrameProxy

    start_iconified_clients = cf.name('WMManager')
    default_pointer_pos = {'Emacs': (-1, 0),
                           'XTerm': (-1, 0)}


class MyScreen(wmanager.Screen,
               color.Color,
               modewindow.ModeWindowScreen,
               modestatus.ModeStatus,
               modestatus.ModeMoveResize,
               views.XMW_ViewHandler,
               modestatus.ModeFocusedTitleScreen):
    """Example screen class

    This class adds support for colors(FIXME), views, and a mode window, and
    adds support to the mode window for displaying status(FIXME: clarify),
    movement and resizing information, the current view, and the title of the
    currently-focused window.

    """
    view_always_visible_clients = f.Or(cf.name('XClock'),
                                       cf.name('XBiff'))

class WMConfig:
    """Example window manager configuration class

    Installs the BasicKeys key map into the window manager.

    TODO: Why is this not included in PLWM below? Should it be moved there?

    """
    def __wm_init__(self):
        # Install the basic key map
        BasicKeys(self)


class PLWM(wmanager.WindowManager,
           font.Font,
           focus.SloppyFocus,
           focus.MoveFocus,
           mw_clock.ModeWindowClock,
           mw_biff.ModeWindowBiff,
           inspect.InspectServer,
           WMConfig):
    """Example window manager class

    This class sets up the configuration for the window manager, including font
    support, sloppy focus, focus movement support, a clock and mail notifier
    for the mode window, and inspection support. It also sets the client class
    and screen class to use.

    """
    client_class = MyClient
    screen_class = MyScreen


class BasicKeys(keys.KeyHandler):
    """Basic key bindings

    This class defines all key-bindings for the example window manager.

    """
    def F1(self, event):
        """Find a view containing an XTerm."""
        self.wm.current_screen.view_find_with_client(cf.name('XTerm'))

    def S_F1(self, event):
        """Start an XTerm."""
        self.wm.system('xterm -geometry 80x50+200+100')

    def C_S_F1(self, event):
        """Start an XTerm in a new view."""
        self.wm.current_screen.view_new()
        self.wm.system('xterm -geometry 80x50+200+100')

    def F2(self, event):
        """Find a view containing an Emacs window."""
        self.wm.current_screen.view_find_with_client(cf.name('Emacs'))

    def S_F2(self, event):
        """Start Emacs."""
        self.wm.system('emacs')

    def C_S_F2(self, event):
        """Start Emacs in a new view."""
        self.wm.current_screen.view_new()
        self.wm.system('emacs')

    def F3(self, event):
        """Find a view containing a Netscape window."""
        self.wm.current_screen.view_find_with_client(cf.name('Firefox'))

    def S_F3(self, event):
        """Start Firefox."""
        self.wm.system('firefox')

    def C_S_F3(self, event):
        """Start Firefox in a new view."""
        self.wm.current_screen.view_new()
        self.wm.system('firefox')

    def F5(self, event):
        """Switch to the next view with the tag 'F5'."""
        self.wm.current_screen.view_find_tag('F5')

    def S_F5(self, event):
        """Set the current view's tag to 'F5'."""
        self.wm.current_screen.view_tag('F5')

    def F6(self, event):
        """Switch to the next view with the tag 'F6'."""
        self.wm.current_screen.view_find_tag('F6')

    def S_F6(self, event):
        """Set the current view's tag to 'F6'."""
        self.wm.current_screen.view_tag('F6')

    def F7(self, event):
        """Switch to the next view with the tag 'F7'."""
        self.wm.current_screen.view_find_tag('F7')

    def S_F7(self, event):
        """Set the current view's tag to 'F7'."""
        self.wm.current_screen.view_tag('F7')

    def F8(self, event):
        """Switch to the next view with the tag 'F8'."""
        self.wm.current_screen.view_find_tag('F8')

    def S_F8(self, event):
        """Set the current view's tag to 'F8'."""
        self.wm.current_screen.view_tag('F8')

    # Simulate mouse clicks
    def Any_F9(self, evt):
        """Simulate a primary (usually, left) mouse button click."""
        self.wm.fake_button_click(1)

    def Any_F10(self, evt):
        """Simulate a secondary (usually, right) mouse button click."""
        self.wm.fake_button_click(2)

    def Any_F11(self, evt):
        """Simulate a tertiary (usually, middle) mouse button click."""
        self.wm.fake_button_click(3)


    def F12(self, evt):
        """Toggle inspect mode."""
        self.wm.inspect_toggle()

    def S_F12(self, evt):
        """Toggle inspect mode, forcing if needed."""
        self.wm.inspect_toggle(force = 1)

    def S_Pause(self, evt):
        """Drop all keygrabs until Scroll_Lock is pressed again.

        Allows clients to recieve keys used by plwm.

        """
        wmanager.debug('keys', 'dropping keygrabs temporarily')

        # First release all our grabs.  They will be reinstalled
        # when BypassHandler exits

        self._ungrab()
        BypassHandler(self)


    def KP_Begin(self, event):
        """Start moving / resizing the current window."""
        MyMoveResizeKeys(self, event)


    def C_Tab(self, event):
        """Cycle through minimized windows."""
        CycleUMKeys(self, event)

    def KP_Insert(self, event):
        """Iconify the current window."""
        wmanager.debug('keys', 'Iconifying')
        if self.wm.current_client:
            self.wm.current_client.iconify()

    def KP_Subtract(self, event):
        """Switch to the previous view."""
        wmanager.debug('keys', 'Prev view')
        self.wm.current_screen.view_prev()

    def KP_Add(self, event):
        """Switch to the next view."""
        wmanager.debug('keys', 'Next view')
        self.wm.current_screen.view_next()

    def C_KP_Add(self, event):
        """Create a new view."""
        wmanager.debug('keys', 'New view')
        self.wm.current_screen.view_new()

    def KP_Left(self, event):
        """Move the pointer to the left."""
        self.wm.display.warp_pointer(-delta.get(event.time), 0)

    def KP_Right(self, event):
        """Move the pointer to the right."""
        self.wm.display.warp_pointer(delta.get(event.time), 0)

    def KP_Up(self, event):
        """Move the pointer up."""
        self.wm.display.warp_pointer(0, -delta.get(event.time))

    def KP_Down(self, event):
        """Move the pointer down."""
        self.wm.display.warp_pointer(0, delta.get(event.time))

    def KP_Home(self, event):
        """Move the pointer up and to the left."""
        d = delta.get(event.time)
        self.wm.display.warp_pointer(-d, -d)

    def KP_End(self, event):
        """Move the pointer down and to the left."""
        d = delta.get(event.time)
        self.wm.display.warp_pointer(-d, d)

    def KP_Prior(self, event):
        """Move the pointer up and to the right."""
        d = delta.get(event.time)
        self.wm.display.warp_pointer(d, -d)

    def KP_Next(self, event):
        """Move the pointer down and to the right."""
        d = delta.get(event.time)
        self.wm.display.warp_pointer(d, d)

    def KP_Enter(self, event):
        """Raise or lower the current window."""
        if self.wm.current_client:
            self.wm.current_client.raiselower()

    # For laptop compitability
    KP_Divide = KP_Enter

    def C_KP_Subtract(self, event):
        """Lock the screen with xlock."""
        self.wm.system('xlock -mode blank')

    def C_M_Escape(self, event):
        """Quit the window manager."""
        self.wm.quit()

    def C_KP_Delete(self, event):
        """Close the current window."""
        if self.wm.current_client:
            self.wm.current_client.delete(1)

    def C_S_KP_Delete(self, event):
        """Kill the current client."""
        if self.wm.current_client:
            self.wm.current_client.destroy()

    def C_KP_Left(self, event):
        """Focus the next window to the left of the current one."""
        self.wm.move_focus(focus.MOVE_LEFT)

    def C_KP_Right(self, event):
        """Focus the next window to the right of the current one."""
        self.wm.move_focus(focus.MOVE_RIGHT)

    def C_KP_Up(self, event):
        """Focus the next window above the current one."""
        self.wm.move_focus(focus.MOVE_UP)

    def C_KP_Down(self, event):
        """Focus the next window below the current one."""
        self.wm.move_focus(focus.MOVE_DOWN)

    def C_less(self, event):
        """Focus the next window to the left of the current one."""
        self.wm.move_focus(focus.MOVE_LEFT)

    def C_S_less(self, event):
        """Focus the next window to the right of the current one."""
        self.wm.move_focus(focus.MOVE_RIGHT)


class BypassHandler(keys.KeyHandler):
    """Surrogate key handler to bypass the window manager's key bindings.

    Allows clients to receive key presses normally handled by the WM.

    """
    propagate_keys = 0

    def __init__(self, keyhandler):
        keys.KeyHandler.__init__(self, keyhandler.wm)
        self._keyhandler = keyhandler
        self._message = modewindow.Message(.1, modewindow.LEFT, 0, '[Bypassing]')
        self._screen = keyhandler.wm.current_screen
        self._screen.modewindow_add_message(self._message)

    def Pause(self, evt):
        """Restore normal key bindings."""
        wmanager.debug('keys', 'reinstalling keygrabs')

        self._screen.modewindow_remove_message(self._message)

        # Delete ourself, and reinstall the callee grabs
        self._cleanup()
        self._keyhandler._buildmap()

        # Remove it, just to be sure there are no circular references
        del self._keyhandler
        del self._screen

#
# Use the keymap for moving and resizing windows.
# Without any modifiers moves, with Shift enlarges, with Ctrl shrinks
# End with KP_5.  Abort with Escape or KP_Delete.
#

class MyMoveResizeKeys(MoveResizeKeys):
    """Keys for moving and resizing the current window."""
    KP_Left  = MoveResizeKeys._move_w
    KP_Right = MoveResizeKeys._move_e
    KP_Up    = MoveResizeKeys._move_n
    KP_Down  = MoveResizeKeys._move_s
    KP_Home  = MoveResizeKeys._move_nw
    KP_End   = MoveResizeKeys._move_sw
    KP_Prior = MoveResizeKeys._move_ne
    KP_Next  = MoveResizeKeys._move_se

    S_KP_Left  = MoveResizeKeys._enlarge_w
    S_KP_Right = MoveResizeKeys._enlarge_e
    S_KP_Up    = MoveResizeKeys._enlarge_n
    S_KP_Down  = MoveResizeKeys._enlarge_s
    S_KP_Home  = MoveResizeKeys._enlarge_nw
    S_KP_End   = MoveResizeKeys._enlarge_sw
    S_KP_Prior = MoveResizeKeys._enlarge_ne
    S_KP_Next  = MoveResizeKeys._enlarge_se

    C_KP_Left  = MoveResizeKeys._shrink_w
    C_KP_Right = MoveResizeKeys._shrink_e
    C_KP_Up    = MoveResizeKeys._shrink_n
    C_KP_Down  = MoveResizeKeys._shrink_s
    C_KP_Home  = MoveResizeKeys._shrink_nw
    C_KP_End   = MoveResizeKeys._shrink_sw
    C_KP_Prior = MoveResizeKeys._shrink_ne
    C_KP_Next  = MoveResizeKeys._shrink_se

    KP_Begin   = MoveResizeKeys._moveresize_end
    S_KP_Begin = MoveResizeKeys._moveresize_end
    C_KP_Begin = MoveResizeKeys._moveresize_end

    Escape    = MoveResizeKeys._moveresize_abort
    KP_Delete = MoveResizeKeys._moveresize_abort


class CycleUMKeys(CycleKeys):
    """Keys to cycle through all iconified windows."""
    _cycle_filter = cf.iconified

    Tab = CycleKeys._cycle_next
    C_Tab = CycleKeys._cycle_next
    S_Tab = CycleKeys._cycle_previous
    S_C_Tab = CycleKeys._cycle_previous

    Escape = CycleKeys._cycle_abort
    Return = CycleKeys._cycle_end


if __name__ == '__main__':
    wmanager.main(PLWM)
