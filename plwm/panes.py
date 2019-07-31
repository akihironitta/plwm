#
# panes.py -- Handle panes (sometimes known as "frames")
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

"""Panes - provide panes to put plwm windows in.

The idea is that each screen is completely covered by panes. Each
pixel on the screen must belong to one and only one pane. Focus
ignores the mouse, but is moved from pane to pane via the
keyboard. Windows open in the current pane, and are told to resize
themselves to fit that pane.

The rest of the UI - well, that's up to you."""

from Xlib import X, Xutil, Xatom
from plwm import wmanager, wmevents, modewindow, cfilter

WM_TRANSIENT_FOR = None
class panesManager:
    "panesManager - pane mixin for window manager."

    panes_window_gravity = X.CenterGravity
    panes_maxsize_gravity = X.CenterGravity
    panes_transient_gravity = X.CenterGravity

    def __wm_screen_init__(self):
        "Create the list of panes with no current pane."
        global WM_TRANSIENT_FOR

        wmanager.debug('panesManager', 'inited')

        # Warning - if we manage more than one display, this breaks!
        if not WM_TRANSIENT_FOR:
            WM_TRANSIENT_FOR = self.display.intern_atom("WM_TRANSIENT_FOR")

        self.panes_list = []
        self.panes_current = None

    def __wm_init__(self):
        "Enable activation, then activate the first pane."

        Pane.activate = Pane.do_activate
        self.panes_list[self.panes_current].activate()

    def panes_add(self, pane):
        "Add the given pane to the list of all panes."

        wmanager.debug('panesManager', 'added pane %s', `pane`)
        self.panes_list.append(pane)
        if self.panes_current is None: self.panes_current = 0

    def panes_remove(self, test):
        "Remove panes that match the filter."

        old = self.panes_list[self.panes_current]
        self.panes_list = filter(cfilter.Not(test), self.panes_list)
        try: self.panes_current = self.panes_list.index(old)
        except ValueError: self.panes_current = 0

    def panes_goto(self, new):
        "Go to the given pane."

        if new == self.panes_current: return
        if 0 <= new < len(self.panes_list):
            self.panes_list[self.panes_current].deactivate()
            self.panes_current = new
            self.panes_list[new].activate()

    def panes_activate(self, pane):
        "Make the given pane the current pane."

        self.panes_goto(self.panes_list.index(pane))

    def panes_next(self):
        "Move to the next pane."

        if len(self.panes_list) > 1:
            wmanager.debug('panesManager', 'next pane')
            self.panes_list[self.panes_current].deactivate()
            self.panes_current = self.panes_current + 1
            if self.panes_current == len(self.panes_list): self.panes_current = 0
            self.panes_list[self.panes_current].activate()

    def panes_prev(self):
        "Move to the previous pane."

        if len(self.panes_list) > 1:
            wmanager.debug('panesManager', 'previous pane')
            self.panes_list[self.panes_current].deactivate()
            self.panes_current = self.panes_current - 1
            if self.panes_current < 0: self.panes_current = len(self.panes_list) - 1
            self.panes_list[self.panes_current].activate()


    def panes_number(self, number):
        "Reorder the panes list so the current pane has the given number."

        self.panes_list[self.panes_current], self.panes_list[number] = \
                                         self.panes_list[number], \
                                         self.panes_list[self.panes_current]
        self.panes_current = number

    # The intent is that if the user has a favorite configuration of panes
    # and windows, that gets set up and then panes_save gets invoked. Later,
    # the windows can be put back in the same panes by invoking panes_restore.
    # I recommend a script that recreates the pane configuration then
    # calls panes_restore be in the config file.
    panes_saved = {}
    def panes_save(self):
        "Record which pane all the windows are in."

        self.panes_saved.clear()
        for client in self.query_clients():
            if client.panes_pane:
                self.panes_saved[client] = self.panes_list.index(client.panes_pane)

    def panes_restore(self):
        "Put the clients back in the saved panes."

        clients = self.query_clients()
        for client in clients:
            pane = self.panes_saved.get(client, None)
            if pane is not None and 0 <= pane < len(self.panes_list) and \
               self.panes_list[pane].screen == client.screen:
                self.panes_list[pane].add_window(client)

        for client in clients:
            if not client.panes_pane: client.iconify()


class panesScreen:
    "paneScreen - pane mixin for Screens."

    def  __screen_client_init__(self):
        "Create the initial pane object for this screen."

        wmanager.debug('panesScreen', 'Initializing screen %d', self.number)
        self.dispatch.add_handler(X.ConfigureRequest, self.panes_configure)
        pane = Pane(self, 0, 0, self.root_width, self.root_height)
        self.panes_fullscreen(pane)
        self.wm.panes_add(pane)

    def panes_fullscreen(self, pane):
        "Make the pane use the all the available screen."

        pane.width = self.root_width
        pane.x = 0
        pane.height = self.root_height
        pane.y = 0

    def panes_configure(self, event):
        "A window changed, so pass it on to my pane."

        w = self.get_window(event.window)
        if w and w.panes_pane:
            if event.value_mask & (X.CWX | X.CWY | X.CWWidth | X.CWHeight):
                w.panes_pane.place_window(w)
            if event.value_mask & X.CWStackMode and event.stack_mode == X.Above \
               and self.allow_self_changes(w):
                w.panes_pane.add_window(w)


class panesClient:
    """panesClient - pane mixin for clients

    Note that this needs to be mixed in *after* any mixins that affect window
    geometry, such as border."""

    def __client_init__(self):
        "Arrange to open in the current pane."

        wmanager.debug('Pane', 'Initing client %s', self)
        # Set this clients gravity
        if self.window.get_property(WM_TRANSIENT_FOR, Xatom.WINDOW, 0, 1) is not None:
            self.panes_gravity = self.wm.panes_transient_gravity
        elif self.sizehints and self.sizehints.flags & Xutil.PMaxSize:
            self.panes_gravity = self.wm.panes_maxsize_gravity
        else:
            self.panes_gravity = self.wm.panes_window_gravity

        self.panes_pointer_pos = self.panes_pane = None
        pane = self.wm.panes_list[self.wm.panes_current]
        if pane.screen != self.screen:
            pane = filter(lambda p, m=self.screen: p.screen == m, self.wm.panes_list)[0]
        pane.add_window(self)
        self.dispatch.add_handler(X.UnmapNotify, self.panes_unmap)
        self.dispatch.add_handler(X.DestroyNotify, self.panes_unmap)

    def panes_unmap(self, event):
        "The window is going away or gone - make sure it's not taking up a pane"

        if self.panes_pane: self.panes_pane.remove_window(self)


class Pane:
    "Pane - the object(s) that manages windows on the screen."

    def __init__(self, screen, x, y, width, height):
        "Initialize a pane of the given size on the given screen."

        self.screen, self.x, self.y, self.width, self.height = screen, x, y, width, height
        self.wm = screen.wm
        self.window = None

    def add_window(self, window):
        "Add a window to this pane."

        wmanager.debug('Pane', 'Adding window %s to pane %s', window, self)
        if window == self.window: return
        old = window.panes_pane
        if old != self:
            if old: old.remove_window(window)
            self.place_window(window)
        window.panes_pane = self
        if self.window: self.deactivate()
        self.window = window
        self.activate()

    def iconify_window(self):
        "Iconify my window, if any."

        if self.window:
            self.window.iconify()
            self.remove_window(self.window)

    def remove_window(self, window):
        "Tag a window as not belonging to me."

        wmanager.debug('Pane', 'Removing window %s from pane %s' % (window, self))
        window.panes_pane = None
        if self.window == window:
            self.deactivate()
            clients = self.screen.query_clients(panefilter(self), 1)
            if not clients: self.window = None
            else:
                self.window = clients[len(clients) - 1]
                if self.wm.panes_list[self.wm.panes_current] == self:
                    self.activate()

    def place_window(self, window = None):
        "Figure out where the window should be put."

        if not window: window = self.window
        wmanager.debug('Pane', 'Placing window %s for pane %s' %
                       (window, self))
        width, height = window.follow_size_hints(self.width - 2 * window.border_width,
                                                 self.height - 2 * window.border_width)

        # If it doesn't fit, just force it.
        if width > self.width - 2 * window.border_width:
            width = self.width - 2 * window.border_width
        if height > self.height - 2 * window.border_width:
            height = self.height - 2 * window.border_width

        if window.panes_gravity in (X.NorthEastGravity, X.EastGravity,
                              X.SouthEastGravity):
            x = self.x
        elif window.panes_gravity in (X.NorthGravity, X.CenterGravity,
                                      X.SouthGravity):
            x = self.x + (self.width - width) / 2 - window.border_width
        else:
            x = self.x + self.width - width - (2 * window.border_width)

        if window.panes_gravity in (X.NorthEastGravity, X.NorthGravity,
                                    X.NorthWestGravity):
            y = self.y
        elif window.panes_gravity in (X.EastGravity, X.CenterGravity,
                                      X.WestGravity):
            y = self.y + (self.height - height) / 2 - window.border_width
        else:
            y = self.y + self.height - height - (2 * window.border_width)

        x, y, width, height = window.keep_on_screen(x, y, width, height)

        wmanager.debug('Pane-configure', 'Resizing window from %d, %d to %d, %d' %
                       (window.width, window.height, width, height))
        window.moveresize(x, y, width, height)

    def force_window(self):
        "Try and force an application to notice what size it's window is."

        if not self.window: return
        self.window.resize(self.width / 2, self.height / 2)
        self.wm.display.flush()
        self.place_window()

    def next_window(self):
        "Move to the next window in this pane."

        wmanager.debug('Pane', 'next window')
        clients = self.screen.query_clients(panefilter(self), 1)
        if len(clients) > 1:
            self.deactivate()
            self.window = clients[0]
            self.activate()

    def prev_window(self):
        "Move to the previous window in this pane."

        wmanager.debug('Pane', 'previous window')
        clients = self.screen.query_clients(panefilter(self), 1)
        if len(clients) > 1:
            self.deactivate()
            # Lower the old window to make it the "next" window.
            self.window.lowerwindow()
            self.window = clients[len(clients) - 2]
            self.activate()

    def deactivate(self):
        "A place to do anything appropriate for us when losing the focus."

        if self.window and not self.window.withdrawn:
            self.window.panes_pointer_pos = self.window.pointer_position()
            if self.wm.panes_list[self.wm.panes_current] == self:
                self.wm.set_current_client(None)

    def activate(self):
        "Dummy function, reset to do_activate after all windows are opened."

    def do_activate(self):
        "Activate whatever is currently my window."

        self.wm.current_screen = self.screen
        if self.window and not self.window.withdrawn:
            wmanager.debug('Pane', 'Activating window %s in pane %s' %
                           (self.window, self))

            # Will raise window and give focus
            self.window.activate()
            pos = self.window.panes_pointer_pos
            if pos:
                self.window.warppointer(pos[0], pos[1])

    def horizontal_split(self, frac = .5):
        "Split the pane horizontally, taking frac off the bottom."

        if frac <= 0 or 1 <= frac:
            raise ValueError, "Pane splits must be between 0 and 1."

        new_height = int(self.height * frac)
        self.height = self.height - new_height
        new_y = self.y + self.height
        map(self.place_window, self.screen.query_clients(panefilter(self)))
        new_pane = Pane(self.screen, self.x, new_y, self.width, new_height)
        self.wm.panes_add(new_pane)
        self.wm.panes_activate(new_pane)

    def vertical_split(self, frac = .5):
        "Split the pane vertically, taking frac off the right."

        if frac <= 0 or 1 <= frac:
            raise ValueError, "Pane splits must be between 0 and 1."

        new_width = int(self.width * frac)
        self.width = self.width - new_width
        new_x = self.x + self.width
        map(self.place_window, self.screen.query_clients(panefilter(self)))
        new_pane = Pane(self.screen, new_x, self.y, new_width, self.height)
        self.wm.panes_add(new_pane)
        self.wm.panes_activate(new_pane)

    def maximize(self):
        "Make me the only pane on my screen."

        self.wm.panes_remove(lambda x, s = self.screen, m = self:
                           x.screen == s and x != m)
        self.screen.panes_fullscreen(self)
        for window in self.screen.query_clients():
            window.panes_pane = self
            self.place_window(window)
        self.activate()

class panefilter:
    "Filter for windows mapped in the current pane."

    def __init__(self, pane):
        "Set the pane we're active in."

        self.pane = pane

    def __call__(self, window):
        "Check to see if this is our pane."

        return self.pane == window.panes_pane and not cfilter.iconified(window)
