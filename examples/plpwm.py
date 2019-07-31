#!/usr/bin/env python
#
# plpwm.py -- Example PLWM window manager configuration with panes.
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

"""plpwm.py - Pointer Less Paned Window Manager

Example PLWM window manager configuration with panes."""

import sys, os, string

###SETUP PATH
sys.path[1:1] = [os.path.join(sys.path[0], '..')]
###END SETUP PATH

from time import sleep
from string import digits

from Xlib import X, XK

from plwm import wmanager, keys, inspect, \
     border, color, font, menu, panes, cfilter, input, message

from plwm.pane_utilities import appmenu, codemenu, windowmenu, panesmenu, \
     runcommand, splitpane, numberpane, pullwindow, gotowindow, websearch, \
     split_pane, getapp, view_menu

from xmlcontrol import XML_controller, load_menus

class MyMenuHandler(menu.MenuCharSelecter):
    Any_Escape = C_g = menu.MenuKeyHandler._abort
    Any_Return = menu.MenuKeyHandler._do
    Any_space = Any_Down = C_n = menu.MenuKeyHandler._down
    Any_BackSpace = Any_Up = C_p = menu.MenuKeyHandler._up


class MyEditHandler(input.InputKeyHandler):
    Any_Escape = C_g = input.InputKeyHandler._abort
    Any_Return = input.InputKeyHandler._done
    Any_Delete = Any_BackSpace = C_h = input.InputKeyHandler._delback
    C_d = input.InputKeyHandler._delforw
    C_b = input.InputKeyHandler._back
    C_f = input.InputKeyHandler._forw
    C_k = input.InputKeyHandler._deltoend
    C_a = input.InputKeyHandler._begin
    C_e = input.InputKeyHandler._end
    C_y = input.InputKeyHandler._paste
    c_p = input.InputKeyHandler._history_up
    c_n = input.InputKeyHandler._history_down


class MyClient(wmanager.Client, border.BorderClient, panes.panesClient):
    "Put the clients in panes, with a border."

    border_default_width = 5
    border_color_name = 'IndianRed4'
    border_focuscolor_name = 'Lawn Green'


class MyScreen(wmanager.Screen,
               color.Color,
               message.screenMessage,
               panes.panesScreen,
               menu.screenMenu):
    "And panes on the screen, and I'm going to want some menus."

    allow_self_changes = cfilter.title('FXTV')
    menu_handler = MyMenuHandler
    menu_bordercolor = "Red"
    message_bordercolor = "Blue"


class WMConfig:
    def __wm_init__(self):
        "install the panes key map, menus, and try to restore my config."

        self.panekeys = PaneKeys(self)
        auto_restore(self, self.panekeys.menus.find('paneconfigmenus'))


class PLPWM(wmanager.WindowManager,
            font.Font,
            panes.panesManager,
            inspect.InspectServer,
            WMConfig):
    "Set up my window manager."

    client_class = MyClient
    screen_class = MyScreen
    panes_maxsize_gravity = X.NorthWestGravity

    def __wm_screen_resize__(self):
        "install the panes key map, menus, and try to restore my config."

        auto_restore(self, self.panekeys.menus.find('paneconfigmenus'))
       

class paneWindow(input.inputWindow):
    bordercolor = "Goldenrod"
    editHandler = MyEditHandler


class screenWindow(input.inputWindow):
    borderwidth = 5
    bordercolor = "Orange"
    editHandler = MyEditHandler


class PaneKeys(keys.KeyHandler):
    "The pane control keys."

    menu_file = os.path.expanduser('~/.plpwmrc.xml')

    def __init__(self, obj):
        keys.KeyHandler.__init__(self, obj)
        self.menus = load_menus(self.menu_file)

    # Commands for navigating and manipulating panes
    def C_0(self, event):
        "Go to the pane numbered by the keycode."

        self.wm.panes_goto(self.wm.display.keycode_to_keysym(event.detail, 0) - XK.XK_0)

    C_1 = C_2 = C_3 = C_4 = C_5 = C_6 = C_7 = C_8 = C_9 = C_0

    def M1_Tab(self, event): self.wm.panes_next()
    def S_M1_Tab(self, event): self.wm.panes_prev()

    def M1_0(self, event):
        pane = self.wm.panes_list[self.wm.panes_current]
        splitpane(pane, pane.horizontal_split, paneWindow)

    def S_M1_0(self, event):
        pane = self.wm.panes_list[self.wm.panes_current]
        splitpane(pane, pane.vertical_split, paneWindow)

    def M1_1(self, event):
        self.wm.panes_list[self.wm.panes_current].maximize()

    def M1_2(self, event):
        split_pane(self.wm.display.keycode_to_keysym(event.detail, 0) - XK.XK_0,
                   self.wm.panes_list[self.wm.panes_current].horizontal_split)

    M1_3 = M1_4 = M1_5 = M1_6 = M1_7 = M1_8 = M1_9 = M1_2

    def S_M1_2(self, event):
        split_pane(self.wm.display.keycode_to_keysym(event.detail, 0) - XK.XK_0,
                   self.wm.panes_list[self.wm.panes_current].vertical_split)

    S_M1_3 = S_M1_4 = S_M1_5 = S_M1_6 = S_M1_7 = S_M1_8 = S_M1_9 = S_M1_2

    def M1_exclam(self, event):
        runcommand(self.wm.panes_list[self.wm.panes_current], paneWindow)

    def M1_equal(self, event):
        numberpane(self.wm.panes_list[self.wm.panes_current], paneWindow)

    def M1_minus(self, event):
        """Close all the internal windows. Untested"""

        for s in self.wm.screens:
            for w in s.windows:
                if self.wm.is_internal_window(w):
                    w.destroy()

    def M1_quoteright(self, event):
        pullwindow(self.wm.panes_list[self.wm.panes_current], paneWindow)

    def M1_quotedbl(self, event):
        gotowindow(self.wm.panes_list[self.wm.panes_current], screenWindow)

    def M1_space(self, event):
        self.wm.panes_list[self.wm.panes_current].prev_window()

    def S_M1_space(self, event):
        self.wm.panes_list[self.wm.panes_current].next_window()

    def _getapp(self, node):
        getapp(self.wm.panes_list[self.wm.panes_current], node.get('title'),
               node.get('command'))

    def M1_a(self, event):
        view_menu(self.wm.panes_list[self.wm.panes_current],
                  XML_controller(self.menus.find('functionmenu'),
                                 dict(getapp=self._getapp)))

    def M1_A(self, event):
        def run(node): self.wm.system('%s &' % node.get('command'))
        view_menu(self.wm.panes_list[self.wm.panes_current],
                  XML_controller(self.menus.find('namemenu'),
                                 dict(getapp=self._getapp, run=run)))

    def M1_c(self, event):
        self.wm.panes_list[self.wm.panes_current].window.delete(1)

    def M1_l(self, event):
        self.wm.system('xscreensaver-command -activate')

    def M1_i(self, event):
        windowmenu(self.wm.panes_list[self.wm.panes_current], cfilter.iconified)

    def M1_I(self, event):
        self.wm.inspect_enable()
        self.wm.system('xterm -title Inspector -e inspect_plwm &')

    def M1_k(self, event):
        self.wm.panes_list[self.wm.panes_current].window.delete(1)

    def M1_K(self, event):
        self.wm.panes_list[self.wm.panes_current].window.destroy()

    def M1_m(self, event):
        def itunes(node): os.system('itunes "%s" &' % node.get('command'))
        view_menu(self.wm.panes_list[self.wm.panes_current],
                  XML_controller(self.menus.find('itunesmenu'),
                                 dict(itunes=itunes)))

    def M1_n(self, event):
        pane = self.wm.panes_list[self.wm.panes_current]
        width, height = pane.screen.message_make("Current pane %d" % \
                                                 self.wm.panes_current)
        pane.screen.message_display((pane.width - width) / 2 + pane.x,
                                   (pane.height - height) / 2 + pane.y)

    def M1_p(self, event):
        panesmenu(self.wm.current_screen)

    def M1_r(self, event):
        self.wm.panes_list[self.wm.panes_current].force_window()

    def M1_R(self, event):
        def reload_menus():
            self.menus = load_menus(self.menu_file)
            auto_restore(self.wm, self.menus.find('paneconfigmenus'))

        def restore_menu(wm):
            view_menu(pane, XML_controller(self.menus.find('paneconfigmenus'),
                                           dict(paneconfig=lambda x: restore(wm, x))))

        pane = self.wm.panes_list[self.wm.panes_current]
        codemenu(pane, {'1: Restore': (restore_menu, (self.wm,)),
                        '2: Reload': (reload_menus, ()),
                        '3: Restart': (os.execvp, (sys.executable,
                                                   [sys.executable] + sys.argv)),
                        '4: Quit': (self.wm.quit, ())
                        })

    def M1_s(self, event):
        def dillo(url):
            self.wm.system("dillo '%s' &" % url)

        def dowebsearch(node):
            if node.get('images'):
                websearch(pane, node.get('label'), paneWindow, node.get('url'),
                          dillo)
            else:
                websearch(pane, node.get('label'), paneWindow, node.get('url'))

        pane = self.wm.panes_list[self.wm.panes_current]
        menu = XML_controller(self.menus.find('websearches'), dict(search=dowebsearch))
        add_keys(menu)
        view_menu(pane, menu)

    def M1_S(self, event):
        self.wm.panes_save()
        pane = self.wm.panes_list[self.wm.panes_current]
        width, height = pane.screen.message_make("Saved panes configuration")
        pane.screen.message_display((pane.screen.root_width - width)
                                     / 2 + pane.screen.root_x,
                                    (pane.screen.root_height - height)
                                     / 2 + pane.screen.root_y)

    def M1_w(self, event):
        windowmenu(self.wm.panes_list[self.wm.panes_current])

    def M1_W(self, event):
        pane = self.wm.panes_list[self.wm.panes_current]
        windowmenu(pane, panes.panefilter(pane))

    def M1_x(self, event):
        self.wm.panes_list[self.wm.panes_current].iconify_window()


def add_keys(menu):
    """Add shortcuts keys to the menu."""

    for label in menu.keys():
        node = menu[label]
        key = node.get('shortcut')
        if key:
            nl = '%s: %s' % (key, label)
            menu[nl] = menu[label]
            del menu[label]


def auto_restore(wm, panes):
    "Look for and restore an automatic config."

    geom = '%dx%d' % (wm.screens[0].root_full_width,
                      wm.screens[0].root_full_height)
    for config in panes:
        startup = config.get('startup')
        if (startup == 'match' and config.get('label').endswith(geom)) or \
               startup == 'use':
            restore(wm, config)
            break

def restore(wm, config):
    "Build my standard work environment."

    wm.panes_list[0].maximize()

    # Disconnect all windows from panes to avoid displaying everything
    # that's about to happen. wm.panes_restore() will put things back.
    for c in wm.query_clients():
        c.panes_pane = None

    # Disconnect any remaining panes from their windows as well.
    wm.panes_list[0].window = None

    places = dict()
    for node in config:
        if node.tag == 'vertical':
            wm.panes_list[wm.panes_current].vertical_split(float(node.get('fraction')))
        elif node.tag == 'horizontal':
            wm.panes_list[wm.panes_current].horizontal_split(float(node.get('fraction')))
        elif node.tag == 'newpane':
            pane = wm.panes_list[int(node.get('pane'))]
        elif node.tag == 'goto':
            wm.panes_goto(int(node.get('pane')))
        elif node.tag == 'number':
            wm.panes_number(int(node.get('new')))
        elif node.tag == 'placewindow':
            places[node.get('name')] = int(node.get('pane'))
        else:
            raise ValueError, 'Unrecognized pane config element %s' % node

    # Now fix any windows wired by title
    panecount = len(wm.panes_list)
    for s in wm.screens:
        for c in s.query_clients(cfilter.true, 1):
            title = c.get_title()
            if title[-2] == '@' and title[-1] in digits:
                pane = digits.index(title[-1])
                if pane < panecount:
                    wm.panes_list[pane].add_window(c)
                    continue
            else:
                for name in places:
                    if name in title:
                        if places[name] < panecount:
                            wm.panes_list[places[name]].add_window(c)
                            break

    # And now make the world sane
    wm.panes_goto(0)
    wm.panes_restore()

if __name__ == '__main__':
    wmanager.main(PLPWM)
