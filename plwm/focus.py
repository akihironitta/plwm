#
# Track which client contains the pointer, and provide some functions for
# moving focus
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


import sys

from Xlib import X, Xutil
import wmanager
import wmevents
import cfilter

MOVE_UP = 1
MOVE_DOWN = 2
MOVE_LEFT = 3
MOVE_RIGHT = 4

class JumpstartClient:
    """Windows get focus when opened.
    """
    def __client_init__(self):
        if not self.start_iconified:
            self.activate()

# WM mixin
class PointToFocus:
    # This mixin tracks focus changes by following EnterNotify and
    # LeaveNotify events on client windows.  WM global event handlers
    # are set up for these events, and whenever a new client is
    # created the corresponding masks are set on it.

    def __wm_init__(self):
        # Handler to set up required X masks on client windows
        self.dispatch.add_handler(wmevents.AddClient,
                                  self.ptfocus_handle_new_client)

        # And handlers for focus tracking
        self.dispatch.add_handler(X.EnterNotify, self.focus_enter)
        self.dispatch.add_handler(X.LeaveNotify, self.focus_leave)

        # Set up initial focus
        self.set_current_client(self.ptfocus_get_focused_client(),
                                X.CurrentTime)

    def ptfocus_handle_new_client(self, evt):
        evt.client.dispatch.set_masks((X.EnterWindowMask, X.LeaveWindowMask))

    # We handle the event by finding the window that contains the
    # pointer, since we get leave events when the pointer leaves the
    # border and enters the window...

    def ptfocus_get_focused_client(self):
        """Return the focused client, or None.

        Override to implement some other focus policy
        Default is that the pointer root is also the focus window.
        """

        # Find the screen and window containing pointer
        for s in self.screens:
            r = s.root.query_pointer()
            if r.same_screen:
                if r.child != None:
                    return s.get_client(r.child)
                else:
                    return None

        return None

    def focus_enter(self, evt):
        wmanager.debug('focus', 'Pointer enter %s', evt.window)
        self.set_current_client(self.ptfocus_get_focused_client(), evt.time)

    def focus_leave(self, evt):
        wmanager.debug('focus', 'Pointer leave %s', evt.window)
        self.set_current_client(self.ptfocus_get_focused_client(), evt.time)

class SloppyFocus(PointToFocus):

    # Variety of PointToFocus, which does not drop focus when the
    # pointer moves to the root window

    def ptfocus_get_focused_client(self):
        client = PointToFocus.ptfocus_get_focused_client(self)

        if client:
            return client
        elif self.focus_client and self.focus_client.is_mapped():
            return self.focus_client
        else:
            return None

# Very trivial focus moving code
class MoveFocus:
    move_focus_ignore_clients = cfilter.false

    def get_client_pos(self, client, dir):
        """Return the position of CLIENT to be used when moving
        focus in direction DIR.
        """

        if dir == MOVE_UP:
            return client.get_bottom_edge()
        elif dir == MOVE_DOWN:
            return client.get_top_edge()
        elif dir == MOVE_LEFT:
            return client.get_right_edge()
        else:
            return client.get_left_edge()

    def move_focus(self, dir):
        """Move focus to the next mapped client in direction DIR.

        DIR is either MOVE_UP, MOVE_DOWN, MOVE_LEFT or MOVE_RIGHT.
        """

        # Get all the mapped clients, if any, sorted in stacking
        # order.  Then inverse the list so the top-most client is
        # first in it.

        if self.current_screen is None:
            return

        clients = self.current_screen.query_clients(cfilter.mapped, stackorder = 1)
        clients.reverse()

        # No clients, meaningless to try to change focus
        if len(clients) == 0:
            return

        # A client is focused, so find the closest client
        if self.focus_client:
            pos = self.get_client_pos(self.focus_client, dir)
            best = None
            bestdiff = None

            for c in clients:
                if c is self.focus_client \
                   or self.move_focus_ignore_clients(c):
                    continue

                p = self.get_client_pos(c, dir)
                if dir == MOVE_UP or dir == MOVE_LEFT:
                    diff = pos - p
                else:
                    diff = p - pos

                # Only use positive diffs, so the clients is on the right
                # side of the focused client
                # If no client has been found, or this diff is smaller
                # than a previous, use this diff as the best
                if diff > 0 and (bestdiff is None or diff < bestdiff):
                    bestdiff = diff
                    best = c


            # Okay, have we found some clients?  Then just use the first found
            # and return.
            if bestdiff != None:
                best.activate()
                return

        # We get here if no client is focused, or if it is the outermost
        # client which is focused.  Get the first client on the opposite
        # side
        best = None
        bestpos = None
        for c in clients:
            if self.move_focus_ignore_clients(c):
                continue

            pos = self.get_client_pos(c, dir)
            if bestpos is None:
                best = c
                bestpos = pos
            elif dir == MOVE_UP or dir == MOVE_LEFT:
                if pos > bestpos:
                    best = c
                    bestpos = pos
            else:
                if pos < bestpos:
                    best = c
                    bestpost = pos

        if best:
            best.activate()


# For backward compitability
class FocusHandler(PointToFocus):
    def __wm_init__(self):
        sys.stderr.write("%s: warning: using deprecated FocusHandler class (use PointToFocus instead)\n" % sys.argv[0])
        PointToFocus.__wm_init__(self)

class FocusClient:
    def __client_init__(self):
        sys.stderr.write("%s: warning: using deprecated FocusClient class (just remove it from mixin list)\n" % sys.argv[0])

