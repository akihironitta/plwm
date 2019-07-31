#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# petliwm.py -- My PLWM "configuration"
#
#    Copyright (C) 1999-2002  Peter Liljenberg <petli@ctrl-c.liu.se>
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


import sys
import os
import re

# Allow running from examples dir in source tree
if os.path.exists(os.path.join(sys.path[0], '../plwm/__init__.py')):
    sys.path[1:1] = [os.path.join(sys.path[0], '..')]


import time

from Xlib import X, XK, Xatom

XK.load_keysym_group('xf86')

from plwm import wmanager, wmevents, \
     focus, keys, \
     deltamove, outline, \
     border, color, font, views, \
     modewindow, modestatus, \
     mw_clock, mw_acpi, \
     mw_watchfiles, \
     inspect, misc, input, \
     composite, mixer, ido

from plwm.moveresize import MoveResizeKeys

import plwm.filters as f
import plwm.cfilter as cf


delta = deltamove.DeltaMove()


class Forcefull:
    def __client_init__(self):
        if self.res_class == 'Tk':
            x, y, w, h = self.keep_on_screen(self.screen.root_x,
                                             self.screen.root_y,
                                             self.screen.root_width,
                                             self.screen.root_height)
            w, h = self.follow_size_hints(w, h)
            self.configure(x = x, y = y, width = w, height = h)


class TraceIM:
    """Class for TraceIMClient.traceim_filters objects.
    """

    def __init__(self, enable, unseen, message):
        """Create a TraceIM filter.

        enable is a client filter selecting the clients that should be
        traced.  It is checked when the client is created.

        unseen is a client filter which is true when there are unseen
        IMs for this client, and then message is displayed in the mode
        window.
        """

        self.enable = enable
        self.unseen = unseen
        self.message = message


class TraceIMClient:

    """Trace IM clients which alter their window title when there's
    new/unread messages.

    Do this by reacting to WM_NAME and iconification changes, applying
    a filter each time.
    """

    # A list of TraceIM objects

    traceim_filters = ()

    def __client_init__(self):
        self.traceim_message = None

        filters = None
        for f in self.traceim_filters:
            if f.enable(self):
                if filters is None:
                    wmanager.debug('traceim', 'Enabling IM tracing for %s' % self.get_title())
                    self.dispatch.add_handler(X.PropertyNotify, self.traceim_handle_property)
                    self.dispatch.add_handler(wmevents.ClientIconified, self.traceim_handle_iconified)
                    self.dispatch.add_handler(wmevents.ClientDeiconified, self.traceim_handle_iconified)
                    self.dispatch.add_handler(wmevents.RemoveClient, self.traceim_handle_removed)
                    filters = [f]
                else:
                    filters.append(f)

        if filters:
            self.traceim_filters = filters
            self.traceim_message = None
            self.traceim_update()

    def traceim_handle_removed(self, evt):
        wmanager.debug('traceim', 'IM tracing window removed')
        del self.traceim_filters[:]
        self.traceim_message = None
        self.wm.traceim_remove_message(self)

    def traceim_handle_property(self, evt):
        if evt.atom == Xatom.WM_NAME:
            self.traceim_update()

    def traceim_handle_iconified(self, evt):
        self.traceim_update()

    def traceim_update(self):
        m = []
        for f in self.traceim_filters:
            if f.unseen(self):
                m.append(f.message)

        if m:
            m = ' '.join(m)
            if m != self.traceim_message:
                wmanager.debug('traceim', 'Unseen IM for %s: %s', self.get_title(), m)
                self.traceim_message = m
                self.wm.traceim_add_message(self, m)
        else:
            if self.traceim_message:
                wmanager.debug('traceim', 'No longer unseen IM for %s', self.get_title())
                self.traceim_message = None
                self.wm.traceim_remove_message(self)


class ModeWindowTraceIM:
    mw_traceim_position = 0.1
    mw_traceim_justification = modewindow.LEFT

    def __wm_screen_init__(self):
        self.mw_traceim_unseen_clients = {}
        self.mw_traceim_message = modewindow.Message(self.mw_traceim_position,
                                                     self.mw_traceim_justification)

    def __wm_init__(self):
        for s in self.screens:
            s.modewindow_add_message(self.mw_traceim_message)

    def traceim_add_message(self, client, message):
        self.mw_traceim_unseen_clients[client] = message
        self.mw_traceim_message.set_text(' '.join(self.mw_traceim_unseen_clients.values()))

    def traceim_remove_message(self, client):
        try:
            del self.mw_traceim_unseen_clients[client]
        except KeyError:
            return

        self.mw_traceim_message.set_text(' '.join(self.mw_traceim_unseen_clients.values()))


class MyClient(wmanager.Client,
               outline.XorOutlineClient,
               border.BorderClient,
               modestatus.ModeFocusedTitleClient,
               misc.InitialKeepOnScreenClient,
               focus.JumpstartClient,
               TraceIMClient,
               ):

#    window_proxy_class = composite.CompositeProxy

    no_border_clients = cf.name('MPlayer')
    full_screen_windows = cf.name('MPlayer')

    start_iconified_clients = cf.name('WMManager')
    default_pointer_pos = {'Emacs': (-5, 5),
                           'XTerm': (-5, 5),
                           'rxvt': (-5, 5),
                           }


    border_default_color = border.FixedBorderColor('grey20', 'grey60')

    traceim_filters = [
        TraceIM(cf.name('Emacs'),                            # KOM runs in Emacs
                f.And(cf.iconified, cf.re_title('Olästa')),  # only when iconified and unread
                'Olästa'),
        ]


class MyScreen(wmanager.Screen,
               color.Color,
               modewindow.ModeWindowScreen,
               modestatus.ModeStatus,
               modestatus.ModeMoveResize,
               views.XMW_ViewHandler,
               modestatus.ModeFocusedTitleScreen):

    view_always_visible_clients = cf.none
    view_reorder_views = 1
    view_reorder_delay = 2.0
    
    #allow_self_changes = none

class WMConfig:
    def __wm_init__(self):
        BasicKeys(self)

        # Add per-screen objects (can't be bothered with a
        # ScreenConfig mixin)

        for screen in self.screens:
            screen.ido_window = MyIdoWindow(screen)


class PLWM(wmanager.WindowManager,
           focus.SloppyFocus,
           focus.MoveFocus,
           font.Font,
           mw_clock.ModeWindowClock,
           mw_acpi.ModeWindowACPI,
           mw_watchfiles.ModeWindowWatchFiles,
           inspect.InspectServer,
           composite.CompositionManager,
           mixer.Mixer,
           ModeWindowTraceIM,
           WMConfig):

    mw_acpi_position = 0
    mw_acpi_justification = modewindow.LEFT

    mw_watchfiles_position = 0.85
    mw_watchfiles_justification = modewindow.RIGHT

    mw_watchfiles = (mw_watchfiles.WatchedFile('/var/run/laptop-mode-tools/enabled',
                                               present_msg = '',
                                               missing_msg = 'LTM off'),

                     # See if pppd is running
                     mw_watchfiles.WatchedFile('/var/run/ppp0.pid',
                                               present_msg = 'ppp'),

                     # Look for a default route
                     mw_watchfiles.WatchedFile('/proc/net/route',
                                               present_msg = 'net',
                                               content_re = re.compile(
                                                   r'^\S+\s+00000000\s',
                                                   re.MULTILINE)),
                     )

    mw_watchfiles_interval = 5

    client_class = MyClient
    screen_class = MyScreen


class MyIdoWindow(ido.IdoWindow):
    window_font = '-*-lucida-medium-r-*-sans-18-*'
    window_foreground = 'white'
    window_background = 'black'
    window_bordercolor = 'red'
    window_borderwidth = 3


class BasicKeys(keys.KeyHandler):
    # WM control

    def M5_z(self, evt):
        self.wm.system('xlock -mode blank')

    def M5_x(self, evt):
        wmanager.debug('keys', 'installing quit keys')
        QuitKeys(self, evt)

    def M5_e(self, evt):
        wmanager.debug('keys', 'running command')
        # misc.RunKeys(self, evt)
        Runcommand(self.wm.current_screen)

    def F12(self, evt):
        self.wm.inspect_toggle()

    def S_F12(self, evt):
        self.wm.inspect_toggle(force = 1)

    # Drop all keygrabs until Scroll_Lock is pressed again, to allow
    # clients to recieve keys used by plwm

    def S_Pause(self, evt):
        wmanager.debug('keys', 'dropping keygrabs temporarily')

        # First release all our grabs.  They will be reinstalled
        # by BypassHandler when it exits
        self._ungrab()
        BypassHandler(self)


    # Window control

    def M5_u(self, evt):
        if self.wm.current_client:
            self.wm.current_client.raiselower()

    def M5_i(self, evt):
        wmanager.debug('keys', 'Iconifying')
        if self.wm.current_client:
            self.wm.current_client.iconify()

    def M5_o(self, evt):
        self.wm.move_focus(focus.MOVE_LEFT)

    def M5_l(self, evt):
        if self.wm.current_client:
            self.wm.current_client.warppointer()

    def M5_k(self, evt):
        MyMoveResizeKeys(self, evt)

    def M5_m(self, evt):
        screen = self.wm.current_screen
        clients = screen.query_clients(cf.iconified, 1)
        clients.reverse()
        screen.ido_window.select(clients, self._ido_select_client)

    def _ido_select_client(self, client):
        if client:
            client.activate()

    def M5_plus(self, evt):
        c = self.wm.current_client
        if c:
            x, y, w, h = c.keep_on_screen(c.screen.root_x,
                                          c.screen.root_y,
                                          c.screen.root_width,
                                          c.screen.root_height)
            w, h = c.follow_size_hints(w, h)
            c.configure(x = x, y = y, width = w, height = h)


    def M5_S_minus(self, evt):
        if self.wm.current_client:
            self.wm.current_client.delete(1)

    def M5_S_C_minus(self, evt):
        if self.wm.current_client:
            self.wm.current_client.destroy()

    # View control

    def F1(self, evt):
        self.wm.current_screen.view_find_with_client(
            f.Or(cf.name('rxvt'), cf.name('xterm')))

    def S_F1(self, evt):
        self.wm.system('rxvt')

    def C_S_F1(self, evt):
        self.wm.current_screen.view_new()
        self.wm.system('rxvt')

    def F2(self, evt):
        self.wm.current_screen.view_find_with_client(cf.name('Emacs'))

    def S_F2(self, evt):
        self.wm.system('emacs')

    def C_S_F2(self, evt):
        self.wm.current_screen.view_new()
        self.wm.system('emacs')

    def F3(self, evt):
        self.wm.current_screen.view_find_with_client(
            f.Or(cf.name('Firefox-bin'),
                 cf.name('Firefox')))

    def S_F3(self, evt):
        self.wm.system('firefox')

    def C_S_F3(self, evt):
        self.wm.current_screen.view_new()
        self.wm.system('firefox')

    def F4(self, evt):
        self.wm.current_screen.view_find_with_client(
            f.Or(cf.name('xpdf'),
                 cf.name('soffice'),
                 cf.re_name('^OpenOffice.org'),
                 cf.name('AcroRead'),
                 cf.name('evince')))

    def F8(self, evt):
        self.wm.current_screen.view_find_with_client(
            f.Or(cf.name('Vmware'),
                 cf.name('Vmplayer')))

    def F5(self, evt):
        self.wm.current_screen.view_find_tag('F5')

    def S_F5(self, evt):
        self.wm.current_screen.view_tag('F5')

    def F6(self, evt):
        self.wm.current_screen.view_find_tag('F6')

    def S_F6(self, evt):
        self.wm.current_screen.view_tag('F6')

    def M5_Prior(self, evt):
        wmanager.debug('keys', 'Prev view')
        self.wm.current_screen.view_prev()

    def M5_Next(self, evt):
        wmanager.debug('keys', 'Next view')
        self.wm.current_screen.view_next()

    def C_M5_Next(self, evt):
        wmanager.debug('keys', 'New view')
        self.wm.current_screen.view_new()

    def M5_n(self, evt):
        wmanager.debug('keys', 'Moving window to new view')
        if self.wm.current_client:
            c = self.wm.current_client
            c.iconify()
            self.wm.current_screen.view_new()
            c.deiconify()


    # Pointer  movements
    def M5_Left(self, evt):
        self.wm.display.warp_pointer(-delta.get(evt.time), 0)

    def M5_Right(self, evt):
        self.wm.display.warp_pointer(delta.get(evt.time), 0)

    def M5_Up(self, evt):
        self.wm.display.warp_pointer(0, -delta.get(evt.time))

    def M5_Down(self, evt):
        self.wm.display.warp_pointer(0, delta.get(evt.time))

    # Simulate mouse clicks
    def Any_F9(self, evt):
        self.wm.fake_button_click(1)

    def Any_F10(self, evt):
        self.wm.fake_button_click(2)

    def Any_F11(self, evt):
        self.wm.fake_button_click(3)

    #
    # Composition effects
    #

    def M5_S_b(self, evt):
        if self.wm.current_client:
            self.wm.comp_change_brightness(self.wm.current_client, 16)

    def M5_b(self, evt):
        if self.wm.current_client:
            self.wm.comp_change_brightness(self.wm.current_client, -16)
            
    def M5_C_b(self, evt):
        if self.wm.current_client:
            self.wm.comp_set_brightness(self.wm.current_client, 0)

    #
    # Mixer control
    #

    # Volume is raised and lowered for both master and pcm in sync:
    # first master is raised by 5%, then pcm by 5%, and likewise when
    # lowering the volume

    def XF86_AudioLowerVolume(self, evt):
        master = self.wm.mixer_get(mixer.MASTER)
        pcm = self.wm.mixer_get(mixer.PCM)

        if master > pcm:
            self.wm.mixer_set(mixer.MASTER, max(master - 5, 0))
        else:
            self.wm.mixer_set(mixer.PCM, max(pcm - 5, 0))
            
        self.wm.mixer_status_view(devs = (mixer.MASTER, mixer.PCM))

    M5_Delete = XF86_AudioLowerVolume
        
    def XF86_AudioRaiseVolume(self, evt):
        master = self.wm.mixer_get(mixer.MASTER)
        pcm = self.wm.mixer_get(mixer.PCM)

        if master <= pcm:
            self.wm.mixer_set(mixer.MASTER, min(master + 5, 100))
        else:
            self.wm.mixer_set(mixer.PCM, min(pcm + 5, 100))
            
        self.wm.mixer_status_view(devs = (mixer.MASTER, mixer.PCM))

    M5_Insert = XF86_AudioRaiseVolume

    def XF86_AudioMute(self, evt):
        self.wm.mixer_mute(mixer.PCM)
        self.wm.mixer_status_view(devs = (mixer.MASTER, mixer.PCM))

    M5_End = XF86_AudioMute

    
class BypassHandler(keys.KeyHandler):
    propagate_keys = 0

    def __init__(self, keyhandler):
        keys.KeyHandler.__init__(self, keyhandler.wm)
        self._keyhandler = keyhandler
        self._message = modewindow.Message(.1, modewindow.LEFT, 0, '[Bypassing]')
        self._screen = keyhandler.wm.current_screen
        self._screen.modewindow_add_message(self._message)

    def Pause(self, evt):
        wmanager.debug('keys', 'reinstalling keygrabs')

        self._screen.modewindow_remove_message(self._message)

        # Delete ourself, and reinstall the callee grabs
        self._cleanup()
        self._keyhandler._buildmap()

        # Remove it, just to be sure there are no circular references
        del self._keyhandler
        del self._screen

class QuitKeys(keys.KeyGrabKeyboard):
    propagate_keys = 0
    timeout = 4

    def __init__(self, keyhandler, evt):
        keys.KeyGrabKeyboard.__init__(self, keyhandler.wm, evt.time)

    def M5_c(self, evt):
        wmanager.debug('keys', 'quitting PLWM')
        self.wm.quit()

    def _timeout(self, evt):
        wmanager.debug('keys', 'cancelling quit keys')
        self.wm.display.bell(100)
        self._cleanup()

    Any_g = _timeout
    Any_Escape = _timeout



class MyMoveResizeKeys(MoveResizeKeys):
    j      = MoveResizeKeys._move_w
    l      = MoveResizeKeys._move_e
    i      = MoveResizeKeys._move_n
    comma  = MoveResizeKeys._move_s
    u      = MoveResizeKeys._move_nw
    m      = MoveResizeKeys._move_sw
    o      = MoveResizeKeys._move_ne
    period = MoveResizeKeys._move_se

    M5_j      = MoveResizeKeys._move_w
    M5_l      = MoveResizeKeys._move_e
    M5_i      = MoveResizeKeys._move_n
    M5_comma  = MoveResizeKeys._move_s
    M5_u      = MoveResizeKeys._move_nw
    M5_m      = MoveResizeKeys._move_sw
    M5_o      = MoveResizeKeys._move_ne
    M5_period = MoveResizeKeys._move_se

    S_j      = MoveResizeKeys._enlarge_w
    S_l      = MoveResizeKeys._enlarge_e
    S_i      = MoveResizeKeys._enlarge_n
    S_comma  = MoveResizeKeys._enlarge_s
    S_u      = MoveResizeKeys._enlarge_nw
    S_m      = MoveResizeKeys._enlarge_sw
    S_o      = MoveResizeKeys._enlarge_ne
    S_period = MoveResizeKeys._enlarge_se

    C_j      = MoveResizeKeys._shrink_w
    C_l      = MoveResizeKeys._shrink_e
    C_i      = MoveResizeKeys._shrink_n
    C_comma  = MoveResizeKeys._shrink_s
    C_u      = MoveResizeKeys._shrink_nw
    C_m      = MoveResizeKeys._shrink_sw
    C_o      = MoveResizeKeys._shrink_ne
    C_period = MoveResizeKeys._shrink_se

    k    = MoveResizeKeys._moveresize_end
    M5_k = MoveResizeKeys._moveresize_end
    g    = MoveResizeKeys._moveresize_abort
    M5_g = MoveResizeKeys._moveresize_abort



class MyEditHandler(input.InputKeyHandler):
    Any_Escape = C_g = input.InputKeyHandler._abort
    Any_Return = input.InputKeyHandler._done
    Any_BackSpace = C_h = input.InputKeyHandler._delback
    C_d = input.InputKeyHandler._delforw
    C_b = input.InputKeyHandler._back
    C_f = input.InputKeyHandler._forw
    C_k = input.InputKeyHandler._deltoend
    C_a = input.InputKeyHandler._begin
    C_e = input.InputKeyHandler._end
    C_y = input.InputKeyHandler._paste


class Runcommand:
    "Read a string from the user, and run it."

    def __init__(self, screen):
        self.screen = screen
        window = input.modeInput("$ ", self.screen)
        window.read(self, MyEditHandler, 0, 0)

    def __call__(self, string):
        self.screen.system(string)


if __name__ == '__main__':
    wmanager.main(PLWM)
