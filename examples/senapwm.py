#!/usr/bin/env python
#
# senapwm.py -- Example PLWM window manager "configuration"
#
#    Copyright (C) 1999,2000  Peter Liljenberg <petli@ctrl-c.liu.se>
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
sys.path[1:1] = [os.path.join(sys.path[0], '/home/morgan/hack/plwm/')]
###END SETUP PATH
from plxlib import plxlib, X
from plwm import wmanager, focus, keys, \
     deltamove, \
     border, color, font, cycle, views, \
     modewinctl, modestatus
from plwm.moveresize import MoveResizeKeys

# from textwindow import TextWindow

delta = deltamove.DeltaMove()

class MyClient(wmanager.Client,
               focus.FocusClient,
               border.BorderClient,
               focus.JumpstartClient,
               modestatus.ModeFocusedTitle):

    no_border_clients = ['XModeWindow']
    start_iconified_clients = ['WMManager']
    move_focus_ignore_clients = no_border_clients
    default_pointer_pos = {'Emacs': (-1, 0),
                           'XTerm': (-1, 0)}


class MyScreen(wmanager.Screen,
               color.Color,
               modewinctl.ModeClientControl,
               modestatus.ModeStatus,
               modestatus.ModeMoveResize,
               views.XMW_ViewHandler,
               keys.KeyGrabber):

    view_always_visible_clients = ['XModeWindow']



class WMConfig:
    def __wm_init__(self):
        BasicKeys(self, self.dispatch)
        self.dispatch.add_handler('cmdevent', cmdhandler)


class PLWM(wmanager.WindowManager,
           focus.SloppyFocus,
           font.Font,
           WMConfig):

    client_class = MyClient
    screen_class = MyScreen


def cmdhandler(evt):
    print 'Exit:', evt.exitstatus(), 'Signal:', evt.termsig()

class BasicKeys(keys.KeyHandler):
    def F1(self, event):
        self.wm.current_screen.view_prev()

    def F2(self, event):
        self.wm.current_screen.view_next()

    def F3(self, event):
        self.wm.move_focus(focus.MOVE_LEFT)

    def F4(self, event):
        self.wm.move_focus(focus.MOVE_RIGHT)

    def KP_End(self, event):
        self.wm.current_screen.view_prev()

    def KP_Down(self, event):
        self.wm.current_screen.view_next()

    def KP_Insert(self, event):
        wmanager.debug('keys', 'New view')
        self.wm.current_screen.view_new()

    def KP_Divide(self, event): #up
        self.wm.move_focus(focus.MOVE_UP)

    def KP_Delete(self, event): #down
        self.wm.move_focus(focus.MOVE_DOWN)

    def KP_Next(self, event): #left
        self.wm.move_focus(focus.MOVE_LEFT)

    def KP_Add(self, event): #right
        self.wm.move_focus(focus.MOVE_RIGHT)

    def S_KP_Divide(self, event): #up
        d = delta.get(event.time)
        self.wm.display.WarpPointer(0, -d)

    def S_KP_Delete(self, event): #down
        d = delta.get(event.time)
        self.wm.display.WarpPointer(0, d)

    def S_KP_Next(self, event): #left
        d = delta.get(event.time)
        self.wm.display.WarpPointer(-d, 0)

    def S_KP_Add(self, event): #right
        d = delta.get(event.time)
        self.wm.display.WarpPointer(d, 0)

    def KP_Subtract(self, event):
        MyMoveResizeKeys(self, event)

    def Pause(self, event):
        self.wm.system('xlock -mode blank')

    def C_M_Escape(self, event):
        raise 'PLWMEscape', 'Escaping window manager'

    def C_KP_Delete(self, event):
        if self.wm.focus_client:
            self.wm.focus_client.delete(1)

    def C_S_KP_Delete(self, event):
        if self.wm.focus_client:
            self.wm.focus_client.destroy()

    def M_section(self, event):
        self.wm.system('xterm')

    def M_F9(self, event):
        self.wm.system('xterm -title Shell -sb -sl 1024 -fn fixed -bg grey70 -fg black')

    def M_F10(self, event):
        self.wm.system('emacs -bg grey70 -fg black')

    def M_F11(self, event):
        self.wm.system('netscape&')



#
# Use the keymap for moving and resizing windows.
#

class MyMoveResizeKeys(MoveResizeKeys):
    KP_Next              = MoveResizeKeys._move_w
    KP_Add               = MoveResizeKeys._move_e
    KP_Divide            = MoveResizeKeys._move_n
    KP_Delete            = MoveResizeKeys._move_s

    C_KP_Next            = MoveResizeKeys._enlarge_w
    C_KP_Add             = MoveResizeKeys._enlarge_e
    C_KP_Divide          = MoveResizeKeys._enlarge_n
    C_KP_Delete          = MoveResizeKeys._enlarge_s

    M_KP_Next            = MoveResizeKeys._shrink_e
    M_KP_Add             = MoveResizeKeys._shrink_w
    M_KP_Divide          = MoveResizeKeys._shrink_s
    M_KP_Delete          = MoveResizeKeys._shrink_n

    KP_Subtract   = MoveResizeKeys._moveresize_end
    S_KP_Subtract = MoveResizeKeys._moveresize_end
    C_KP_Subtract = MoveResizeKeys._moveresize_end




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

