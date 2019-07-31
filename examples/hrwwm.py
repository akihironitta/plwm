#!/usr/bin/env python
#
# hrwwm.py -- Example PLWM window manager "configuration"
#
#    Copyright (C) 1999,2000  Peter Liljenberg <petli@ctrl-c.liu.se>
#                             Henrik Rindlöw <rindlow@lysator.liu.se>
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
###SETUP PATH
sys.path[1:1] = [os.path.join(sys.path[0], '..')]
###END SETUP PATH
from plxlib import plxlib, X
from plwm import wmanager, focus, keys, \
     moveresize, deltamove, \
     border, color, font, cycle, views, \
     modewinctl, modetitle

delta = deltamove.DeltaMove()

class MyClient(wmanager.Client,
               focus.FocusClient,
               border.BorderClient,
               modetitle.ModeTitleClient):

    no_border_clients = ['XClock', 'XBiff', 'CDStatus', 'XModeWindow']
    start_iconified_clients = ['WMManager']
    move_focus_ignore_clients = no_border_clients
    default_pointer_pos = {'Emacs': (-1, 0),
                           'XTerm': (-1, 0)}


class ScreenConfig:
    pass
#    def __screen_client_init__(self):
#        self.set_color('BorderFocusColor', 'grey60')


class MyScreen(wmanager.Screen,
               color.Color,
               modewinctl.ModeClientControl,
               views.XMW_ViewHandler,
               keys.KeyGrabber,
               ScreenConfig):

    view_always_visible_clients = ['XClock', 'XBiff', 'CDStatus', 'XModeWindow']



class WMConfig:
#    def __wm_screen_init__(self):
#        self.set_font('OutlineNameFont', '-*-lucida-bold-r-*-sans-20-*-*-*-*-*-*-*')

    def __wm_init__(self):
        BasicKeys(self, self.dispatch)


class PLWM(wmanager.WindowManager,
           focus.SloppyFocus,
           font.Font,
           WMConfig):

    client_class = MyClient
    screen_class = MyScreen


class BasicKeys(keys.KeyHandler):
#     def F5(self, event):
#         wins = self.wm.root.QueryTree()[2]
#         for w in wins:
#             c = self.wm.get_client(w)
#             if c and c.is_mapped():
#                 c.raisewindow()
#                 c.warppointer()
#                 return

    def F1(self, event):
        self.wm.current_screen.view_find_with_client('XTerm')

    def S_F1(self, event):
        self.wm.system('xterm -geometry 80x50+200+100')

    def C_S_F1(self, event):
        self.wm.current_screen.view_new()
        self.wm.system('xterm -geometry 80x50+200+100')

    def F2(self, event):
        self.wm.current_screen.view_find_with_client('Emacs')

    def S_F2(self, event):
        self.wm.system('emacs')

    def C_S_F2(self, event):
        self.wm.current_screen.view_new()
        self.wm.system('emacs')

    def F3(self, event):
        self.wm.current_screen.view_find_with_client('Netscape')

    def S_F3(self, event):
        self.wm.system('netscape')

    def C_S_F3(self, event):
        self.wm.current_screen.view_new()
        self.wm.system('netscape')

    def F4(self, event):
        self.wm.current_screen.view_find_with_client('applix')

    def KP_Begin(self, event):
        wmanager.debug('keys', 'Entering move-resize mode')
        if self.wm.focus_client:
            try:
                mv = MoveResizeKeys(self.wm, self.dispatch,
                                    self.wm.focus_client, event.time)
            except keys.error, status:
                wmanager.debug('keys', 'Grabbing keyboard failed: %d', status)
    KP_5 = KP_Begin

    def C_Tab(self, event):
        wmanager.debug('keys', 'Into CycleUnmapped mode')
        try:
            mv = CycleUMKeys(self.wm, self.dispatch, event.time)
        except keys.error, status:
            wmanager.debug('keys', 'Grabbing keyboard failed: %d', status)

    def KP_Insert(self, event):
        wmanager.debug('keys', 'Iconifying')
        if self.wm.focus_client:
            self.wm.focus_client.iconify()
    KP_0 = KP_Insert

    def KP_Subtract(self, event):
        wmanager.debug('keys', 'Prev view')
        self.wm.current_screen.view_prev()

    def KP_Add(self, event):
        wmanager.debug('keys', 'Next view')
        self.wm.current_screen.view_next()

    def C_KP_Add(self, event):
        wmanager.debug('keys', 'New view')
        self.wm.current_screen.view_new()

    def KP_Left(self, event):
        self.wm.display.WarpPointer(-delta.get(event.time), 0)
    KP_4 = KP_Left

    def KP_Right(self, event):
        self.wm.display.WarpPointer(delta.get(event.time), 0)
    KP_6 = KP_Right

    def KP_Up(self, event):
        self.wm.display.WarpPointer(0, -delta.get(event.time))
    KP_8 = KP_Up

    def KP_Down(self, event):
        self.wm.display.WarpPointer(0, delta.get(event.time))
    KP_2 = KP_Down

    def KP_Home(self, event):
        d = delta.get(event.time)
        self.wm.display.WarpPointer(-d, -d)
    KP_7 = KP_Home

    def KP_End(self, event):
        d = delta.get(event.time)
        self.wm.display.WarpPointer(-d, d)
    KP_1 = KP_End

    def KP_Prior(self, event):
        d = delta.get(event.time)
        self.wm.display.WarpPointer(d, -d)
    KP_9 = KP_Prior

    def KP_Next(self, event):
        d = delta.get(event.time)
        self.wm.display.WarpPointer(d, d)
    KP_3 = KP_Next

    def KP_Enter(self, event):
        if self.wm.focus_client:
            self.wm.focus_client.configure({'stack_mode': X.Opposite})

    def C_KP_Subtract(self, event):
        self.wm.system('xlock -mode blank')

    def C_M_Escape(self, event):
        raise 'PLWMEscape', 'Escaping window manager'

    def C_KP_Delete(self, event):
        if self.wm.focus_client:
            self.wm.focus_client.delete(1)
    C_KP_Separator= C_KP_Delete

    def C_S_KP_Delete(self, event):
        if self.wm.focus_client:
            self.wm.focus_client.destroy()
    C_S_KP_Separator= C_S_KP_Delete

    def C_KP_Left(self, event):
        self.wm.move_focus(focus.MOVE_LEFT)
    C_KP_ = C_KP_Left

    def C_KP_Right(self, event):
        self.wm.move_focus(focus.MOVE_RIGHT)
    C_KP_6 = C_KP_Right

    def C_KP_Up(self, event):
        self.wm.move_focus(focus.MOVE_UP)
    C_KP_8 = C_KP_Up

    def C_KP_Down(self, event):
        self.wm.move_focus(focus.MOVE_DOWN)
    C_KP_2 = C_KP_Down

    def C_less(self, event):
        self.wm.move_focus(focus.MOVE_LEFT)

    def C_S_less(self, event):
        self.wm.move_focus(focus.MOVE_RIGHT)


class MoveResizeKeys(keys.KeyGrabKeyboard):
    propagate_keys = 0
    timeout = 20

    def __init__(self, wm, dispatch, client, time):
        keys.KeyGrabKeyboard.__init__(self, wm, dispatch, time)
        self.mv = moveresize.MoveResizeOutline(client, delta)

    def KP_Left(self, event):
        self.mv.move(-delta.get(event.time), 0)
    KP_4 = KP_Left

    def KP_Right(self, event):
        self.mv.move(delta.get(event.time), 0)
    KP_6 = KP_Right

    def KP_Up(self, event):
        self.mv.move(0, -delta.get(event.time))
    KP_8 = KP_Up

    def KP_Down(self, event):
        self.mv.move(0, delta.get(event.time))
    KP_2 = KP_Down

    def KP_Home(self, event):
        d = delta.get(event.time)
        self.mv.move(-d, -d)
    KP_7 = KP_Home

    def KP_End(self, event):
        d = delta.get(event.time)
        self.mv.move(-d, d)
    KP_1 = KP_End

    def KP_Prior(self, event):
        d = delta.get(event.time)
        self.mv.move(d, -d)
    KP_9 = KP_Prior

    def KP_Next(self, event):
        d = delta.get(event.time)
        self.mv.move(d, d)
    KP_3 = KP_Next

    def S_KP_Left(self, event):
        self.mv.resizeunits(-1, 0, 1, 0, event.time)
    S_KP_4 = S_KP_Left

    def S_KP_Right(self, event):
        self.mv.resizeunits(0, 0, 1, 0, event.time)
    S_KP_6 = S_KP_Right

    def S_KP_Up(self, event):
        self.mv.resizeunits(0, -1, 0, 1, event.time)
    S_KP_8 = S_KP_Up

    def S_KP_Down(self, event):
        self.mv.resizeunits(0, 0, 0, 1, event.time)
    S_KP_2 = S_KP_Down

    def S_KP_Home(self, event):
        self.mv.resizeunits(-1, -1, 1, 1, event.time)
    S_KP_7 = S_KP_Home

    def S_KP_End(self, event):
        self.mv.resizeunits(-1, 0, 1, 1, event.time)
    S_KP_1 = S_KP_End

    def S_KP_Prior(self, event):
        self.mv.resizeunits(0, -1, 1, 1, event.time)
    S_KP_9 = S_KP_Prior

    def S_KP_Next(self, event):
        self.mv.resizeunits(0, 0, 1, 1, event.time)
    S_KP_3 = S_KP_Next

    def C_KP_Left(self, event):
        self.mv.resizeunits(1, 0, -1, 0, event.time)
    C_KP_4 = C_KP_Left

    def C_KP_Right(self, event):
        self.mv.resizeunits(0, 0, -1, 0, event.time)
    C_KP_6 = C_KP_Right

    def C_KP_Up(self, event):
        self.mv.resizeunits(0, 1, 0, -1, event.time)
    C_KP_8 = C_KP_Up

    def C_KP_Down(self, event):
        self.mv.resizeunits(0, 0, 0, -1, event.time)
    C_KP_2 = C_KP_Down

    def C_KP_Home(self, event):
        self.mv.resizeunits(1, 1, -1, -1, event.time)
    C_KP_7 = C_KP_Home

    def C_KP_End(self, event):
        self.mv.resizeunits(1, 0, -1, -1, event.time)
    C_KP_1 = C_KP_End

    def C_KP_Prior(self, event):
        self.mv.resizeunits(0, 1, -1, -1, event.time)
    C_KP_9 = C_KP_Prior

    def C_KP_Next(self, event):
        self.mv.resizeunits(0, 0, -1, -1, event.time)
    C_KP_3 = C_KP_Next

    def KP_Begin(self, event):
        wmanager.debug('keys', 'Leaving move-resize mode')
        self.mv.end()
        self._cleanup()
    KP_5 = KP_Begin

    S_KP_Begin = KP_Begin
    C_KP_Begin = KP_Begin

    def Escape(self, event):
        wmanager.debug('keys', 'Aborting move-resize mode')
        self.mv.abort()
        self._cleanup()

    _timeout = Escape
    KP_Delete = Escape


class CycleUMKeys(keys.KeyGrabKeyboard):
    propagate_keys = 0
    timeout = 10

    def __init__(self, wm, dispatch, time):
        keys.KeyGrabKeyboard.__init__(self, wm, dispatch, time)
        self.cy = cycle.CycleUnmapped(wm.current_screen, 1)

    def Tab(self, event):
        self.cy.next()

    C_Tab = Tab

    def S_Tab(self, event):
        self.cy.previous()

    def Return(self, event):
        wmanager.debug('keys', 'Escaping CycleMapped mode')
        self._cleanup()
        self.cy.end()

    def Escape(self, event):
        wmanager.debug('keys', 'Aborting CycleMapped mode')
        self._cleanup()
        self.cy.abort()

    _timeout = Escape

if __name__ == '__main__':
    sync = 0
    while len(sys.argv) > 1:
        if sys.argv[1] == '-d':
            wmanager.debug = wmanager.do_debug
        elif sys.argv[1] == '-s':
            sync = 1
        del sys.argv[1]

    try:
        p = PLWM()
    except wmanager.error_no_unmanaged_screens:
        sys.stderr.write(sys.argv[0] + ': Another window manager already running?\n')
        sys.exit(1)

    if sync:
        p.display.Synchronize(1)
    p.brave_loop()

