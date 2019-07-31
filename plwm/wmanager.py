#
# wmanager.py -- core window manager functionality
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
import signal
import errno
import array
import traceback
import re
import string
import types
import time

from Xlib import display, X, Xutil, Xatom, rdb, error
import Xlib.protocol.event

import plwm
import event
import wmevents
import filters

# Minimum Xlib version
required_xlib_version = (0, 14)

# Errors
class UnavailableScreenError(Exception): pass
class NoUnmanagedScreensError(Exception): pass
class BadXlibVersion(Exception): pass


# Debugging

debug_file = sys.stderr
debug_what = []

debug_start_time = time.time()

def do_debug(what, fmt, *args):
    if not debug_what or what in debug_what:
        debug_file.write('%8.3f %s: %s\n' % (
            time.time() - debug_start_time, what, (fmt % args)))

def dont_debug(*args):
    pass

debug = dont_debug


class Window:
    """Class representing any window object on a screen, either internal
    or client windows.
    """

    full_screen_windows = filters.none

    def __init__(self, screen, window):
        "Create a window object managing WINDOW."

        self.screen = screen
        self.window = window
        self.wm = screen.wm        # So we can pass Windows to KeyHandlers.

        self.withdrawn = 0
        self.delayed_moveresize = 0

        self.current = 0
        self.focused = 0

        self.force_iconified = 0

        self.event_mask = event.EventMask(window)

        self.dispatch = event.WindowDispatcher(self.event_mask)

        # Initial mapped state and geometry
        a = window.get_attributes()
        self.mapped = a.map_state != X.IsUnmapped

        r = self.window.get_geometry()
        self.x = r.x
        self.y = r.y
        self.width = r.width
        self.height = r.height
        self.border_width = r.border_width


    def __str__(self):
        return '<%s %s>' % (self.__class__, self.window)

    def __repr__(self):
        return self.__str__()

    #
    # Internal methods
    #

    def withdraw(self, destroyed = 0):
        """Window has been withdrawn.
        If DESTROYED is true the window doesn't exist anymore."""

        if self.withdrawn:
            return

        self.mapped = 0
        self.withdrawn = 1

        # Don't listen to any more X events on this window
        if not destroyed:
            self.event_mask.clear()
        
        # Clear the dispatcher to avoid cirkular references
        self.dispatch = event.SlaveDispatcher([])


    def handle_event(self, event, grabbed = 0):
        """Handle EVENT for this client by calling its dispatch table.
        """
        self.dispatch.handle_event(event, grabbed)


    def get_focus(self, time):
        debug('focus', 'client gets focus: %s', self)
        self.focused = 1
        self.window.set_input_focus(X.RevertToPointerRoot, time)

    def lose_focus(self):
        debug('focus', 'client loses focus: %s', self)
        self.focused = 0

    #
    # External methods
    #

    def configure(self, **keys):
        if self.withdrawn:
            return

        for i in ['x', 'y', 'width', 'height', 'border_width']:
            setattr(self, i, keys.get(i, getattr(self, i)))

        apply(self.window.configure, (), keys)


    def is_mapped(self):
        return self.mapped

    def valid_window(self):
        """Return true if the window still exists.
        """
        if self.withdrawn:
            return 0

        # Check for an invalid window by trigging BadDrawable
        # on a simple request
        try:
            r = self.window.get_geometry()
        except error.BadDrawable:
            return 0
        else:
            return 1

    def resize(self, width, height):
        if self.withdrawn:
            return
        self.window.configure(width = width, height = height)
        self.width = width
        self.height = height


    def move(self, x, y):
        if self.withdrawn:
            return
        self.window.configure(x = x, y = y)
        self.x = x
        self.y = y


    def moveresize(self, x, y, width, height, delayed = 0):
        if self.withdrawn:
            return

        # If client is iconified and delayed is true, don't actually
        # resize the window now but postpone it until deiconifying
        if self.mapped or not delayed:
            self.window.configure(x = x, y = y, width = width, height = height)
            self.delayed_moveresize = 0
        else:
            self.delayed_moveresize = 1

        self.x = x
        self.y = y
        self.width = width
        self.height = height


    def setborderwidth(self, width):
        if self.withdrawn:
            return
        self.window.configure(border_width = width)
        self.border_width = width


    def set_border_color(self, color):
        if self.withdrawn:
            return

        self.window.change_attributes(border_pixel = color)


    def keep_on_screen(self, x, y, width, height):
        """Return X, Y, WIDTH, HEIGHT after adjusting so the entire window
        is visible on the screen, including the border.
        """

        if self.full_screen_windows(self):
            root_x = 0
            root_y = 0
            root_width = self.screen.root_full_width
            root_height = self.screen.root_full_height
        else:
            root_x = self.screen.root_x
            root_y = self.screen.root_y
            root_width = self.screen.root_width
            root_height = self.screen.root_height

        # negative sizes is impossible
        if width < 0:
            width = 0
        if height < 0:
            height = 0

        # width and height must not be larger than the screen area
        if width + 2 * self.border_width > root_width:
            width = root_width - 2 * self.border_width
        if height + 2 * self.border_width > root_height:
            height = root_height - 2 * self.border_width

        # Move window if right/bottom edge is outside screen
        if (x + width + 2 * self.border_width
            > root_x + root_width):
            x = (root_x + root_width
                 - width - 2 * self.border_width)

        if (y + height + 2 * self.border_width
            > root_y + root_height):
            y = (root_y + root_height
                 - height - 2 * self.border_width)

        # Move window if left/top edge is outside screen
        if x < root_x:
            x = root_x
        if y < root_y:
            y = root_y

        return x, y, width, height

    def geometry(self):
        return self.x, self.y, self.width, self.height, self.border_width

    def get_top_edge(self):
        """Return the y coordinate of the top edge of the client."""
        return self.y

    def get_bottom_edge(self):
        """Return the y coordinate of the bottom edge of the client."""
        return self.y + self.height + 2 * self.border_width

    def get_left_edge(self):
        """Return the x coordinate of the left edge of the client."""
        return self.x

    def get_right_edge(self):
        """Return the x coordinate of the right edge of the client."""
        return self.x + self.width + 2 * self.border_width

    def pointer_position(self):
        """Return the pointer x and y position relative to the window
        origin.  Return None if the pointer is on another screen.
        """
        if self.withdrawn:
            return None

        # Handle destroyed windows gracefully, registering the error
        # so the window is withdrawn from managing.

        try:
            r = self.window.query_pointer()
        except error.BadWindow, e:
            self.wm.events.put_event(e)
            return None

        if r.same_screen:
            return r.win_x, r.win_y
        else:
            return None

    #
    # Window ops
    #

    def map(self):
        if self.withdrawn: return None

        # Perform delayed resizing
        if self.delayed_moveresize:
            self.window.configure(x = self.x, y = self.y,
                                  width = self.width,
                                  height = self.height)
            self.delayed_moveresize = 0

        self.window.map()

    def unmap(self):
        if self.withdrawn: return None
        self.window.unmap()

    def clear_area(self, *args, **keys):
        if self.withdrawn: return None
        apply(self.window.clear_area, args, keys)

    def fill_rectangle(self, gc, x, y, width, height, onerror = None):
        if self.withdrawn: return None
        self.window.fill_rectangle(gc, x, y, width, height, onerror)

    def image_text(self, gc, x, y, string, onerror = None):
        if self.withdrawn: return None
        self.window.image_text(gc, x, y, string, onerror)

    def draw_text(self, gc, x, y, text, onerror = None):
        if self.withdrawn: return None
        self.window.draw_text(gc, x, y, text, onerror)

    def convert_selection(self, selection, target, property, time, onerror = None):
        if self.withdrawn: return None
        self.window.convert_selection(selection, target, property, time, onerror)

    def destroy(self):
        if self.withdrawn:
            return
        self.screen.remove_window(self.window)
        self.window.destroy()

    def raisewindow(self):
        if self.withdrawn:
            return
        self.window.configure(stack_mode = X.Above)

    def lowerwindow(self):
        if self.withdrawn:
            return
        self.window.configure(stack_mode = X.Below)

    def raiselower(self):
        if self.withdrawn:
            return
        self.window.configure(stack_mode = X.Opposite)


class InternalWindow(Window):
    pass

class Client(Window):
    "Container for clients of the window manager."

    start_iconified_clients = filters.none
    default_pointer_pos = {}
    client_maxsize = {}

    # set below to avoid circular imports
    needs_reparent_clients = None

    window_proxy_class = None
    
    def __init__(self, screen, window, maprequest):
        """Create a client object managing WINDOW.

        If MAPPED is true, this client has been created
        because of a MapRequest event.  If false, it was created
        when the window manager started and scanned available
        windows.
        """

        if Client.needs_reparent_clients is None:
            # now we can import cfilter safely
            import cfilter
            Client.needs_reparent_clients = cfilter.name('AWTapp')
            del cfilter

        # Let any window proxy in on the fun
        if self.window_proxy_class is not None:
            window = self.window_proxy_class(screen, window)
            
        Window.__init__(self, screen, window)

        # Let proxy register event handlers now that we have a dispatcher 
        if self.window_proxy_class is not None:
            window.__proxy_event_init__(self)

        self.window.change_save_set(X.SetModeInsert)

        self.from_maprequest = maprequest

        # Set up the system event handlers

        self.dispatch.add_system_handler(X.DestroyNotify, self.handle_destroy_notify)
        self.dispatch.add_system_handler(X.UnmapNotify, self.handle_unmap_notify)
        self.dispatch.add_system_handler(X.PropertyNotify, self.handle_property_notify)

        # Fetch WM hints
        self.wmhints = self.window.get_wm_hints()
        self.sizehints = self.window.get_wm_normal_hints()
        self.protocols = self.window.get_wm_protocols()

        hint = self.window.get_wm_class()
        if hint:
            self.res_name, self.res_class = hint
        else:
            self.res_name = self.res_class = None


        # Some broken widget sets (e.g. Java AWT) checks whether a
        # window manager is running, and if so, will do nothing until
        # they receive the ReparentNotify that indicates that their
        # window has now been put into a frame by the wm.  Because
        # PLWM does not have frame windows, this breaks horribly.

        # To cater for AWT and its demented cousins, we reparent the
        # window to be at the same position in the root window.  This
        # is effectively a no-op, but will generate the
        # ReparentNotify.  It can also generates an UnmapNotify, so
        # block that event.

        if self.needs_reparent_clients(self):
            debug('client', 'reparenting incompetent window')
            self.event_mask.block(X.StructureNotifyMask)
            self.screen.event_mask.block(X.SubstructureNotifyMask)

            self.window.reparent(self.screen.root, self.x, self.y)

            self.screen.event_mask.unblock(X.SubstructureNotifyMask)
            self.event_mask.unblock(X.StructureNotifyMask)


        # Detect client focus model

        # Always call set_input_focus, unless the client has set input
        # hint to false

        if self.wmhints is not None \
           and self.wmhints.flags & Xutil.InputHint \
           and not self.wmhints.input:
            self.do_set_focus = 0
        else:
            self.do_set_focus = 1

        # We send message if client supports the WM_TAKE_FOCUS protocol
        if self.wm.WM_TAKE_FOCUS in self.protocols:
            self.do_send_focus_msg = 1

            # However: we always set focus of globally active windows,
            # to avoid having to track FocusIn/FocusOut.
            if not self.do_set_focus:
                self.do_set_focus = 1
        else:
            self.do_send_focus_msg = 0


        # Figure out if we should start iconified or not

        # First: if the window is mapped from a withdrawn state
        # use the WM hints state hint if present

        if maprequest and self.wmhints and self.wmhints.flags & Xutil.StateHint \
           and self.wmhints.initial_state == Xutil.IconicState:
            self.start_iconified = 1

        # Second: start iconified if the client already is iconic
        elif self.get_wm_state() == Xutil.IconicState:
            self.start_iconified = 1

        # Third : start iconified if the clients matches
        # start_iconified_clients
        elif self.start_iconified_clients(self):
            self.start_iconified = 1

        # Otherwise start mapped, although this can be overridden
        else:
            self.start_iconified = 0

        # Now find and call all __client_init__ methods
        call_inits(self.__class__, '__client_init__', self)


    def __del__(self):
        # Just call all __client_del__ methods
        call_inits(self.__class__, '__client_del__', self)

    #
    # Internal methods
    #

    def withdraw(self, destroyed = 0):
        """Window has been withdrawn.
        If DESTROYED is true the window doesn't exist anymore."""

        if self.withdrawn:
            return

        Window.withdraw(self, destroyed)
        if not destroyed:
            self.window.change_save_set(X.SetModeDelete)
            self.window.delete_property(self.wm.WM_STATE)

        # Pass note to proxy, if any, that the window is gone
        if self.window_proxy_class is not None:
            self.window._proxy_withdraw()

        
    def handle_property_notify(self, event):
        """Called when a property has changed on the client window.
        EVENT is a PropertyEvent object.
        """
        if self.withdrawn:
            return

        # The only ICCCM property we should follow is WM_NORMAL_HINTS,
        # as that one can change e.g. when changing font in an Emacs.
        # The other properties should be set before the window is
        # mapped, and mostly affect initial state anyway.

        if event.atom == Xatom.WM_NORMAL_HINTS:

            # Handle destroyed windows gracefully, registering the error
            # so the window is withdrawn from managing.

            try:
                self.sizehints = self.window.get_wm_normal_hints()
            except error.BadWindow, e:
                self.wm.events.put_event(e)

    def handle_destroy_notify(self, event):
        debug('clientnotify', 'Destroy of window %s', event.window)
        self.wm.remove_window(event.window, 1)

    def handle_unmap_notify(self, event):
        debug('clientnotify', 'Unmapping window %s', event.window)
        self.wm.remove_window(event.window)

    def initial_map(self):
        """Called after creating a client to map its window."""

        debug('client', 'start_iconified: %d' % self.start_iconified)
        if self.start_iconified:
            self.iconify()
        else:
            self.deiconify()

    def get_focus(self, time):
        debug('focus', 'client gets focus: %s', self)
        self.focused = 1
        self.wm.events.put_event(wmevents.ClientFocusIn(self))
        if self.do_set_focus:
            self.window.set_input_focus(X.RevertToPointerRoot, time)
        if self.do_send_focus_msg:
            self.send_message(self.wm.WM_TAKE_FOCUS, time)

    def lose_focus(self):
        debug('focus', 'client loses focus: %s', self)
        self.wm.events.put_event(wmevents.ClientFocusOut(self))
        self.focused = 0


    #
    # External methods
    #

    def configure(self, **keys):
        if self.client_maxsize.has_key(self.res_name):
            maxsize = self.client_maxsize[self.res_name]
        elif self.client_maxsize.has_key(self.res_class):
            maxsize = self.client_maxsize[self.res_class]
        else:
            maxsize = None

        if keys.has_key('width') and maxsize:
            keys['width'] = min(keys['width'], maxsize[0])

        if keys.has_key('height') and maxsize:
            keys['height'] = min(keys['height'], maxsize[1])

        apply(Window.configure, (self, ), keys)


    def iconify(self):
        if self.withdrawn:
            return

        debug('client', 'iconify')
        
        # Prevent us from recieving UnmapNotify events
        self.event_mask.block(X.StructureNotifyMask)
        self.screen.event_mask.block(X.SubstructureNotifyMask)

        self.unmap()

        self.screen.event_mask.unblock(X.SubstructureNotifyMask)
        self.event_mask.unblock(X.StructureNotifyMask)

        self.mapped = 0
        self.window.set_wm_state(state = Xutil.IconicState, icon = 0)
        self.wm.events.put_event(wmevents.ClientIconified(self))


    def deiconify(self):
        if self.withdrawn:
            return

        if self.force_iconified:
            return

        if self.force_iconified:
            return
        
        debug('client', 'deiconify')
        
        self.map()
        self.mapped = 1
        self.window.set_wm_state(state = Xutil.NormalState, icon = 0)
        self.wm.events.put_event(wmevents.ClientDeiconified(self))


    def delete(self, destroy = 0):
        if self.withdrawn:
            return

        if self.wm.WM_DELETE_WINDOW in self.protocols:
            self.send_message(self.wm.WM_DELETE_WINDOW)
        elif destroy:
            self.destroy()

    def activate(self):
        """Make this client active by raising it's window and moving
        the pointer into it.
        """
        if self.withdrawn:
            return

        if not self.mapped:
            self.deiconify()

        ### FIXME:  This really could be done so much prettier to
        ### avoid having to upset the window stacking order.
        self.raisewindow()
        self.warppointer()

        # Explicitly set focus, in case we use a non-pointer-based
        # focus method
        self.wm.set_current_client(self)

    def send_message(self, atom, time = X.CurrentTime, args = []):
        if self.withdrawn:
            return
        if len(args) > 3:
            args = args[:3]
        elif len(args) < 3:
            args = args + [0] * (3 - len(args))

        ev = Xlib.protocol.event.ClientMessage(window = self.window,
                                               client_type = self.wm.WM_PROTOCOLS,
                                               data = (32, ([atom, time] + args)))
        self.window.send_event(ev)


    def resize_increment(self):
        if self.sizehints and self.sizehints.flags & Xutil.PResizeInc:
            return self.sizehints.width_inc, self.sizehints.height_inc
        else:
            return 0, 0

    def base_size(self):
        if self.sizehints and self.sizehints.flags & Xutil.PBaseSize:
            return self.sizehints.base_width, self.sizehints.base_height
        else:
            return 0, 0

    def follow_size_hints(self, width, height):
        w = width
        h = height

        if self.sizehints:
            sh = self.sizehints

            # Fix resize increment stuff
            if sh.flags & Xutil.PResizeInc:

                # Find base size
                if sh.flags & Xutil.PBaseSize:
                    base_width = sh.base_width
                    base_height = sh.base_height

                # If no base size is provided, the minimum size should
                # be used instead, it that is provided
                elif sh.flags & Xutil.PMinSize:
                    base_width = sh.min_width
                    base_height = sh.min_height

                # Else no base size at all
                else:
                    base_width = 0
                    base_height = 0


                w = width - base_width
                h = height - base_height

                wi = w % sh.width_inc
                if wi != 0:
                    if 2 * wi >= sh.width_inc:
                        w = w + sh.width_inc - wi
                    else:
                        w = w - wi
                hi = h % sh.height_inc
                if hi != 0:
                    if 2 * hi >= sh.height_inc:
                        h = h + sh.height_inc - hi
                    else:
                        h = h - hi

                if self.full_screen_windows(self):
                    root_width = self.screen.root_full_width
                    root_height = self.screen.root_full_height
                else:
                    root_width = self.screen.root_width
                    root_height = self.screen.root_height

                # Make sure the window fits on screen
                rw = root_width - base_width - 2 * self.border_width
                rh = root_height - base_height - 2 * self.border_width

                if w > rw:
                    w = rw - rw % sh.width_inc
                if h > rh:
                    h = rh - rh % sh.height_inc

                w = w + base_width
                h = h + base_height


            # Use minimum size if provided
            if sh.flags & Xutil.PMinSize:
                if w < sh.min_width:
                    w = sh.min_width
                if h < sh.min_height:
                    h = sh.min_height

            # Fall back to base size if that is provided
            elif sh.flags & Xutil.PBaseSize:
                if w < sh.base_width:
                    w = sh.base_width
                if h < sh.base_height:
                    h = sh.base_height

            # Use maximum size, but there's no fallback
            if sh.flags & Xutil.PMaxSize:
                if w > sh.max_width:
                    w = sh.max_width
                if h > sh.max_height:
                    h = sh.max_height

            # Fixing aspect ratio?  Nah.  Not now.

        return w, h


    def warppointer(self, x = None, y = None):
        """Warp the pointer to the coordinate (X, Y) in this window.

        X and Y are the coordinates to move the pointer to.  Positive values
        count from top/left edges, negative values from the
        bottom/right edges (the "negative" origo is (-1, -1)).

        If X and Y is omitted, warp to the default position (which
        normally is the middle of the window.

        A different default position can be stored in the mapping
        Client.default_pointer_pos.  The key is the res_name or res_class
        of the window, the value a tuple of two integers: the x and y coordinates.
        """
        if self.withdrawn:
            return

        # Get default position, if needed
        if x == None or y == None:
            if self.default_pointer_pos.has_key(self.res_name):
                x, y = self.default_pointer_pos[self.res_name]
            elif self.default_pointer_pos.has_key(self.res_class):
                x, y = self.default_pointer_pos[self.res_class]
            else:
                x = self.width / 2
                y = self.height / 2

        # Handle negative positions
        if x < 0:
            x = self.width + x - 1
        if y < 0:
            y = self.height + y - 1

        # Make sure that the pointer is inside the window
        if x < 0:
            x = 0
        elif x >= self.width:
            x = self.width - 1
        if y < 0:
            y = 0
        elif y >= self.height:
            y = self.height - 1

        self.window.warp_pointer(x, y)


    def fetch_name(self):
        if self.withdrawn:
            return None

        # Handle destroyed windows gracefully, registering the error
        # so the window is withdrawn from managing.
        try:
            return self.window.get_wm_name()
        except error.BadWindow, e:
            self.wm.events.put_event(e)
            return None


    def get_title(self):
        """Return an appropriate title for this client.
        """
        name = self.fetch_name()
        if not name:
            if self.res_name:
                name = self.res_name
            else:
                name = '<untitled>'
        return name


    def get_wm_state(self):
        if self.withdrawn:
            return Xutil.WithdrawnState

        try:
            r = self.window.get_wm_state()
        except error.BadWindow, e:
            self.wm.events.put_event(e)
            return None

        if r:
            return r.state
        else:
            return None


class Screen:
    allow_self_changes = filters.all

    def __init__(self, wm, screenno):
        self.wm = wm
        self.number = screenno
        self.info = self.wm.display.screen(screenno)

        # Fetch root window and important values
        self.root = self.wm.display.screen(self.number).root
        g =  self.root.get_geometry()
        self.root_x = 0
        self.root_y = 0
        self.root_width = g.width
        self.root_height = g.height
        self.root_full_width = g.width
        self.root_full_height = g.height

        self.windows = {}

        # Map proxy windows to actual windows
        self.proxy_windows = {}
        
        self.event_mask = event.EventMask(self.root)

        # Set up event handler for this screen
        self.dispatch = event.WindowDispatcher(self.event_mask)

        ec = error.CatchError(error.BadAccess)
        self.event_mask.set(X.SubstructureRedirectMask, onerror = ec)

        # And sync here, so we catch any errors caused by
        # failing to set SubstructureRedirectMask
        self.wm.display.sync()

        err = ec.get_error()
        if err:
            # Another wm already manages this screen: cancel
            raise UnavailableScreenError(err)

        # Fix a DISPLAY string for this screen by replacing the
        # screen number in the DISPLAY with this screen's number
        
        dstr = self.wm.display.get_display_name()
        m = re.search(r'(:\d+)(\.\d+)?$', dstr)
        if m:
            self.displaystring = dstr[:m.end(1)] + '.' + str(self.number)
        else:
            self.displaystring = dstr

        # Set up all the system handlers.

        # Handlers for the redirect events.  We don't want to update the masks
        # as we explicitly set those masks above.
        self.dispatch.add_system_handler(X.MapRequest,
                                         self.handle_map_request,
                                         masks = ())

        self.dispatch.add_system_handler(X.ConfigureRequest,
                                         self.handle_configure_request,
                                         masks = ())

        self.dispatch.add_system_handler(X.CirculateRequest,
                                         self.handle_circulate_request,
                                         masks = ())
        self.dispatch.add_system_handler(X.ClientMessage,
                                          self.handle_client_message)

        # Track screen changes
        self.dispatch.add_system_handler(X.EnterNotify, self.handle_screen_enter)
        self.dispatch.add_system_handler(X.ConfigureNotify, self.handle_screen_change)

        call_inits(self.__class__, '__screen_client_init__', self)

        # Find all clients, ignoring transient windows (override_redirect).
        r = self.root.query_tree()
        wins = r.children

        # Weed out icon windows (thanks to ctwm for the idea...)
        for w in wins[:]:
            wmh = w.get_wm_hints()
            if wmh and wmh.flags & Xutil.IconWindowHint:
                try:
                    wins.remove(wmh.icon_window)
                except ValueError:
                    pass

        # Then add any mapped window, or windows with non-withdrawn
        # WM_STATE property, unless it has override_redirect set.
        # Skip internal windows.

        for w in wins:
            a = w.get_attributes()
            r = w.get_wm_state()
            if (a.map_state != X.IsUnmapped
                or (r and r.state in (Xutil.NormalState, Xutil.IconicState))) \
                and not a.override_redirect \
                and not self.is_internal_window(w):

                self.add_client(w, 0)

        call_inits(self.__class__, '__screen_init__', self)

    def __del__(self):
        # Just call all __screen_del__ methods
        call_inits(self.__class__, '__screen_del__', self)

    def add_client(self, window, maprequest):
        """Add a client managing WINDOW.

        Returns 1 if a client was added, 0 if it was already managed.
        """
        if self.is_client(window):
            return 0
        else:
            debug('clients', 'Adding client for %s', window)
            client = self.wm.client_class(self, window, maprequest)

            # Use what client think its window is, to handle proxy windows
            self.windows[client.window] = client

            client.initial_map()
            self.wm.events.put_event(wmevents.AddClient(client))
            return 1

    def remove_window(self, window, destroyed = 0):
        """Remove the Window objet handling WINDOW.
        If DESTROYED is true, WINDOW doesn't exist anymore.
        """

        debug('window', 'Removing window for %s', window)

        wobj = self.get_window(window)

        if wobj is None:
            return

        # If it is a Client object, post a RemoveClient event.  As
        # that will not reach the client object, dispatch it manually.
        # Also, this must be done before withdrawing the window, as
        # that kills the event dispatcher.
        if isinstance(wobj, Client):
            debug('clientnotify', 'Sending RemoveClient for %s', window)
            evt = wmevents.RemoveClient(wobj)
            self.wm.events.put_event(evt)
            wobj.handle_event(evt)

        wobj.withdraw(destroyed)

        del self.windows[window]

    def add_internal_window(self, window):
        self.windows[window] = InternalWindow(self, window)
        return self.windows[window]

    def get_client(self, window):
        c = self.get_window(window)
        if isinstance(c, Client):
            return c
        else:
            return None

    def get_window(self, window):
        """Translate an Xlib window object into its controlling Window
        or Client object.

        Returns None if the Xlib window isn't known. 
        """

        while window is not None:
            try:
                return self.windows[window]
            except KeyError:
                # Try to translate via proxy window
                window = self.proxy_windows.get(window, None)

        return None


    def is_client(self, window):
        return isinstance(self.get_window(window), Client)
    

    def is_internal_window(self, window):
        return isinstance(self.get_window(window), InternalWindow)


    def add_proxy_window(self, proxy, window):
        """Add a proxy window, so that get_window() on PROXY leads on
        to WINDOW to find the actual Window object.
        """
    
        self.proxy_windows[proxy] = window


    def remove_proxy_window(self, proxy):
        """Remove a proxy window previously registered with add_proxy_window().
        """
    
        del self.proxy_windows[proxy]
        

    def query_clients(self, client_filter = filters.all, stackorder = 0):
        """Return a list of clients on this screen matching CLIENT_FILTER.

        By default, all clients are returned in no particular order.
        But if STACKORDER is true, the clients will be returned in their
        current stacking order, lowest client first.
        """

        if stackorder:
            wins = self.root.query_tree().children
            clients = []
            for w in wins:
                c = self.get_client(w)
                if c and client_filter(c):
                    clients.append(c)

            return clients
        else:
            # Use the internal filter function, but filter
            # out non-client windows by augmenting the client
            # filter
            import cfilter
            return filter(filters.And(cfilter.is_client,
                                      client_filter),
                          self.windows.values())

    def alloc_border(self, edge, size):
        """Allocate a part of the outmost area of the root to display
        wm info in.  Clients will not infringe on this area.

        EDGE is one of 'top', 'bottom', 'left', or 'right', indicating
        on which edge of the root the area should be placed against.
        SIZE is the height or width of the area, depending on EDGE.

        The return value is a tuple, giving the coordinates of the
        allocated area: (x, y, width, height)
        """

        if edge == 'top':
            assert size < self.root_height

            c =  (self.root_x, self.root_y, self.root_width, size)

            self.root_height = self.root_height - size
            self.root_y = self.root_y + size

            return c

        elif edge == 'bottom':
            assert size < self.root_height

            self.root_height = self.root_height - size
            return (self.root_x, self.root_y + self.root_height,
                    self.root_width, size)

        elif edge == 'left':
            assert size < self.root_width

            c =  (self.root_x, self.root_y, size, self.root_height)

            self.root_width = self.root_width - size
            self.root_x = self.root_x + size

            return c

        elif edge == 'right':
            assert size < self.root_height

            self.root_width = self.root_width - size
            return (self.root_x + self.root_width, self.root_y,
                    size, self.root_height)

        else:
            raise TypeError('bad edge value: %s' % edge)


    def handle_event(self, event, window = None, grabbed = 0):
        grabbed = self.dispatch.handle_event(event, grabbed)

        if window:
            window.handle_event(event, grabbed)

    def handle_map_request(self, event):
        debug('redirect', 'Maprequest for client %s', event.window)
        # add the client, unless it already is managed
        if not self.add_client(event.window, 1):
            # already mapped window, map it if the user allows it
            w = self.get_client(event.window)
            if self.allow_self_changes(w):
                w.map()

    def event_to_change(self, event):
        change = {}
        if event.value_mask & X.CWX:
            change['x'] = event.x
        if event.value_mask & X.CWY:
            change['y'] = event.y
        if event.value_mask & X.CWWidth:
            change['width'] = event.width
        if event.value_mask & X.CWHeight:
            change['height'] = event.height
        w = self.get_window(event.window)
        if w and self.allow_self_changes(w):
            if event.value_mask & X.CWSibling:
                change['sibling'] = event.above
            if event.value_mask & X.CWStackMode:
                change['stack_mode'] = event.stack_mode
        return change

    def handle_configure_request(self, event):
        w = self.get_window(event.window)
        if w:
            debug('redirect', 'ConfigureRequest for window %s', event.window)
            apply(w.configure, (), self.event_to_change(event))
        else:
            debug('redirect', 'ConfigureRequest for unmanaged window %s', event.window)
            apply(event.window.configure, (), self.event_to_change(event))

    def handle_circulate_request(self, event):
        debug('redirect', 'CirculateRequest for %s', event.window)
        w = self.get_window(event.window)
        if not (w and self.allow_self_changes(w)):
            return

        if event.place == X.PlaceOnTop:
            if w:
                w.raisewindow()
            else:
                event.window.configure(stack_mode = X.Above)
        elif event.place == X.PlaceOnBottom:
            if w:
                w.lowerwindow()
            else:
                event.window.configure(stack_mode = X.Below)

    def handle_client_message(self, event):
        debug('client', 'client sent us a message: %s', event)
        w = self.get_client(event.window)
        if w is None:
            return
        if event.client_type == self.wm.WM_CHANGE_STATE and \
           event.data[1][0] == Xutil.IconicState and \
           self.allow_self_changes(w):
            w.iconify()

    def handle_screen_enter(self, event):
        # Mouse has entered this screen from another screen
        # iff these conditions are true:
        if event.window == self.root \
           and event.detail in (X.NotifyNonlinear, X.NotifyNonlinearVirtual):
            self.wm.current_screen = self

    def handle_screen_change(self, event):
        """The screen changed geometry. Cool."""

        if event.window == self.root and \
               (self.root_full_width != event.width or \
                self.root_full_height != event.height):

            self.root_full_width = self.root_width = event.width 
            self.root_full_height = self.root_height = event.height
            self.wm.handle_screen_resize(event)

    def system(self, cmd, fg = 0, evt = None, redirect = None):
        """Run the shell command CMD, with DISPLAY set to this screen.

        CMD is run in the background by default, but is FG is true
        this call will block until it has finished.

        If EVT is not None, it should be a CommandEvent or subclass.
        This event will be put on the event queue when CMD exits.  EVT
        is ignored though if FG is true.

        If REDIRECT is given, it should be either a single integer 0
        to 2, or a tuple of them.  These file descriptors will
        be redirected into pipes allowing the caller to capture the
        data.  The pipes are returned as file objects in a
        three-tuple, with index N corresponding the the redirected
        file descriptor N.  REDIRECT implies background execution.

        Returns None if CMD is run in the background and REDIRECT is
        None, if it is run in the foreground the exit status of CMD is
        returned as encoded by system().
        """

        # purge collected exit statuses of non-event children
        del self.wm.children_exit_status[:]

        if redirect is not None:
            if type(redirect) is not types.TupleType:
                redirect = (redirect, )

            fg = 0
            pipes = [None, None, None]
            for fd in redirect:
                if fd < 0 or fd > 2:
                    raise ValueError('redirect file descriptor should be 0-2: %s' % fd)
                if pipes[fd]:
                    raise ValueError('redirect file descriptor should not be repeated: %s' % redirect)

                pipes[fd] = os.pipe()


        pid = os.fork()
        if pid == 0:
            # Create new process group for the child, so it doesn't
            # get the signals sent to the parent process
            os.setpgid(0, 0)

            # Child process, run the command with a little help from sh
            os.environ['DISPLAY'] = self.displaystring
            try:
                # dup and close pipes on the child end
                if redirect:
                    if pipes[0]:
                        r, w = pipes[0]
                        os.close(w)
                        os.dup2(r, 0)
                        os.close(r)

                    if pipes[1]:
                        r, w = pipes[1]
                        os.close(r)
                        os.dup2(w, 1)
                        os.close(w)

                    if pipes[2]:
                        r, w = pipes[2]
                        os.close(r)
                        os.dup2(w, 2)
                        os.close(w)

                os.execlp('sh', 'sh', '-c', cmd)
            except os.error, msg:
                # Failed to run the program
                sys.stderr.write('%s: %s: %s\n' % (sys.argv[0], cmd, str(msg)))
                os._exit(127)

        else:
            # Parent, should we block here?
            if fg:
                # check if child still exists
                try:
                    p2, status = os.waitpid(pid, os.WNOHANG)
                    if p2 == pid:
                        return status
                except os.error, val:
                    if val.errno != errno.ECHILD:
                        raise val

                    # it is gone, grab error from collected exit
                    # statuses
                    for p2, status in self.wm.children_exit_status:
                        if pid == p2:
                            return status

                    # odd, the exit status have disappeared
                    raise RuntimeError("foreground children exit status has gone, this can't happen!")


                # otherwise we must loop until the children exits
                while 1:
                    # We must catch EINTR errors to avoid exceptions
                    # when recieving SIGCHLD.
                    try:
                        signal.pause()
                    except os.error, val:
                        raise val
                        if val.errno not in (errno.EINTR, errno.ECHILD):
                            raise val

                    for p2, status in self.wm.children_exit_status:
                        if pid == p2:
                            return status

            else:
                # FIXME: possible race condition here, should handle through
                # children_exit_status as above but can't be bothered
                # until something actually uses child events.
                if evt:
                    self.wm.add_command_event(pid, evt)

                if redirect:
                    # close pipes and create file objects
                    # on the parent end
                    if pipes[0]:
                        r, w = pipes[0]
                        os.close(r)
                        pipes[0] = os.fdopen(w, 'w')

                    if pipes[1]:
                        r, w = pipes[1]
                        os.close(w)
                        pipes[1] = os.fdopen(r, 'r')

                    if pipes[2]:
                        r, w = pipes[2]
                        os.close(w)
                        pipes[2] = os.fdopen(r, 'r')

                    return pipes
                else:
                    return None


    #
    # Cyclops circular reference detecting support
    #
    def _register_cycle_roots(self, cyclefinder):
        """Called by the corresponding function in WindowManager.
        """

        # We just add all the clients
        for c in self.clients.values():
            cyclefinder.register(c)

    def _cleanup_cycle_roots(self):
        """Called by the corresponding function in WindowManager.
        """
        for c in self.clients.values():
            self.remove_client(c.window, 1)


class WindowManager:
    client_class = Client
    screen_class = Screen

    appclass = 'Plwm'

    def __init__(self, disp, appname, db):
        """WindowManager(display, appname, rdb)

        Create a WindowManager object.
        """

        self.display = disp
        self.appname = appname
        self.rdb = db

        # Set up some atoms not defined in Xatom
        self.WM_DELETE_WINDOW = self.display.intern_atom('WM_DELETE_WINDOW')
        self.WM_PROTOCOLS = self.display.intern_atom('WM_PROTOCOLS')
        self.WM_STATE = self.display.intern_atom('WM_STATE')
        self.WM_TAKE_FOCUS = self.display.intern_atom('WM_TAKE_FOCUS')
        self.WM_CHANGE_STATE = self.display.intern_atom('WM_CHANGE_STATE')
        debug('atoms', 'DELETE_WINDOW: %s\tPROTOCOLS: %s\tSTATE: %s\t' \
              'TAKE_FOCUS: %s\t, CHANGE_STATE: %s',
              self.WM_DELETE_WINDOW, self.WM_PROTOCOLS, self.WM_STATE,
              self.WM_TAKE_FOCUS, self.WM_CHANGE_STATE)

        if display is not None:
            os.environ['DISPLAY'] = self.display.get_display_name()

        # Set up the event handling.
        self.events = event.EventFetcher(self.display)

        # Install handlers for child processes
        self.child_events = {}
        self.children_exit_status = []
        self.old_sigchld_handler = signal.signal(signal.SIGCHLD,
                                                 self.sigchld_handler)
        if self.old_sigchld_handler in (signal.SIG_IGN, signal.SIG_DFL):
            self.old_sigchld_handler = None


        # current_client is the client which currently contains the
        # pointer, and on which window operations should take placce.

        # focus_client is the client which actually holds the input
        # focus.

        self.current_client = None
        self.focus_client = None

        # Setup a default focus policy, which can be overridden later
        self.display.set_input_focus(X.NONE, X.PointerRoot, X.RevertToPointerRoot)

        # Set up a screen-indepentend event handler
        self.dispatch = event.SlaveDispatcher([])

        # Call mixin initialisation needed before adding screens
        call_inits(self.__class__, '__wm_screen_init__', self)

        # Find all the screens
        self.screens = []
        self.screen_nums = {}
        self.screen_roots = {}
        for sno in range(0, self.display.screen_count()):
            try:
                s = self.screen_class(self, sno)
                self.screens.append(s)
                self.screen_nums[sno] = s
                self.screen_roots[s.root] = s
                self.dispatch.add_master(s.dispatch)

            # This screen is already managed by some other
            # window manager, print a message and skip it
            except UnavailableScreenError:
                sys.stderr.write('%s: Screen %d already managed by some other window manager\n' % (sys.argv[0], sno))

        # If we cant find any screens, abort now
        if not self.screens:
            raise NoUnmanagedScreensError('another window manager already running?')

        try:
            self.default_screen = self.screen_nums[self.display.get_default_screen()]
        except KeyError:
            self.default_screen = self.screens[0]

        # Find the current screen
        self.current_screen = self.default_screen
        for s in self.screens:
            if s.root.query_pointer().same_screen:
                self.current_screen = s
                break

        # Handle to refresh the keyboard mapping information
        self.dispatch.add_system_handler(X.MappingNotify,
                                         self.handle_mapping_notify)

        # Handle errors caused by destroyed windows
        self.display.set_error_handler(self.x_error_handler)

        # Call all final mixin constructors
        call_inits(self.__class__, '__wm_init__', self)

    def __del__(self):
        # Just call all __wm_del__ methods
        call_inits(self.__class__, '__wm_del__', self)

    def loop(self):
        """Loop indefinitely, handling events.
        """
        while 1:
            event = self.events.next_event()
            self.handle_event(event)
            if event.type == wmevents.QuitWindowManager:
                self.display.sync()
                return

    def brave_loop(self, max_exc = 10):
        """Loop indefinitely, handling events.

        If an exception occur, catch it and print a traceback.
        Contiune processing events while less than MAX_EXC exceptions
        has occured.
        """
        exc = 0
        while 1:
            try:
                event = self.events.next_event()
                self.handle_event(event)
                if event.type == wmevents.QuitWindowManager:
                    self.display.sync()
                    return

            # Pass on keyboardinterrupt, exiting loop
            except KeyboardInterrupt:
                raise

            # Print all other exceptions and continue
            except:
                if exc < max_exc:
                    apply(traceback.print_exception, sys.exc_info())
                    exc = exc + 1
                else:
                    raise sys.exc_info()[0], sys.exc_info()[1]

    def quit(self):
        """Quit PLWM, or at least return to caller of loop()
        or brave_loop().
        """

        self.events.put_event(wmevents.QuitWindowManager())


    def handle_events(self):
        """Handle all the events on the queue.
        """
        while 1:
            event = self.events.next_event(timeout = 0)
            if event is None:
                return
            self.handle_event(event)


    def remove_window(self, window, destroyed = 0):
        """Remove the Window object of WINDOW.
        If DESTROYED is true, the window doesn't exist anymore.
        """
        w = self.get_window(window)
        if w is not None:
            w.screen.remove_window(window, destroyed)

    def get_client(self, window):
        for s in self.screens:
            c = s.get_client(window)
            if c:
                return c

        return None

    def get_window(self, window):
        for s in self.screens:
            w = s.get_window(window)
            if w:
                return w

        return None

    def is_client(self, window):
        for s in self.screens:
            if s.is_client(window):
                return 1
        return 0

    def is_internal_window(self, window):
        for s in self.screens:
            if s.is_internal_window(window):
                return 1
        return 0

    def query_clients(self, client_filter = filters.all, stackorder = 0):
        """Return a list of clients on all screens, matching CLIENT_FILTER.

        By default, all clients are returned sorted by their screen
        number, but with no additional sorting.

        If STACKORDER is true, the clients will be returned in their
        current stacking order, lowest client first.
        """

        clients = []
        for s in self.screens:
            clients = clients + s.query_clients(client_filter, stackorder)

        return clients


    def x_error_handler(self, err, request):
        """Handle window errors by telling the client than it
        is withdrawn.
        """

        sys.stderr.write('X protocol error:\n%s\n' % err)
        
        if isinstance(err, error.BadWindow) or isinstance(err, error.BadDrawable):
            # The error can't be handled immediately, as the error
            # handler must not call any Xlib methods.  Solve this by
            # queing up the error object on the event queue and
            # checking for this in the event handler just below.

            # The event queue doesn't care about us putting an XError
            # there, it just returns it to us.

            self.events.put_event(err)


    def handle_event(self, event):

        """Handle EVENT by dispatching to registered handlers.

        First handlers for the WindowManager as whole is called,
        followed by the handlers for each of the managed screen's root
        window.  Then if the events corresponds to a client, call its
        handlers.  A grab handler for the window manager prevents any
        grab and normal handlers for the client to be called.
        """

        debug('verbose_event', 'handling %s', event)

        # Continuation of the error handling hack: check if this is a
        # window error and if so remove it
        if isinstance(event, error.BadWindow) or isinstance(event, error.BadDrawable):
            self.remove_window(event.resource_id, 1)
            return


        grabbed = self.dispatch.handle_event(event)

        if hasattr(event, 'client') and event.client:
            event.client.screen.handle_event(event, event.client, grabbed)
            return

        if hasattr(event, 'window'):
            window = event.window
            # Find the correct screen.

            # First check if the event window is
            # the root window or is an already handled client for
            # some screen
            for s in self.screens:
                if window == s.root:
                    s.handle_event(event, None, grabbed)
                    return

                w = s.get_window(window)
                if w:
                    s.handle_event(event, w, grabbed)
                    return

            # Unknown window, ask for it's root window
            if window:
                try:
                    root = window.get_geometry().root
                    s = self.screen_roots[root]
                # Bad window, or unmanaged screen, just abort
                except (error.BadDrawable, KeyError):
                    pass
                else:
                    s.handle_event(event, None, grabbed)

            return

        # Event destined for specific screen
        if hasattr(event, 'screen') and event.screen:
            event.screen.handle_event(event, None, grabbed)

        # Unmanaged screen, ignore
        return


    def handle_mapping_notify(self, event):
        debug('keys', 'MappingNotify event')
        self.display.refresh_keyboard_mapping(event)


    def handle_screen_resize(self, event):
        # The default window manager does nada; but let mixins know

	call_inits(self.__class__, '__wm_screen_resize__', self)

    def set_current_client(self, client, time = X.CurrentTime, force_focus = 0):
        """Set the current client to CLIENT, occuring at the X event
        TIME.

        This will update the WindowManager.current_client and
        Client.current of the affected clients.  A CurrentClientChange
        event will be sent with the new current client.

        CLIENT can also be None, meaning that now no client is the
        current one.

        If the client accepts focus, or FORCE_FOCUS is true, CLIENT
        will get the focus, and WindowManager.focus_client and
        Client.focused will be changed.  ClientFocusOut and
        ClientFocusIn events will be sent.
        """

        # Will the new current client also get focus?
        # If client is None, we treat that as getting focus
        if client:
            getfocus = (client.do_set_focus or force_focus)
        else:
            getfocus = 1

        # If focus will change, drop focus from the old focused client

        if getfocus and self.focus_client and self.focus_client != client:
            self.focus_client.lose_focus()
            self.focus_client = None

        # If current client changes, update that

        if self.current_client != client:
            if self.current_client:
                self.current_client.current = 0
                screen = self.current_client.screen
            else:
                screen = None

            if client:
                client.current = 1

            self.current_client = client
            self.events.put_event(wmevents.CurrentClientChange(screen, client))
            debug('focus', 'current client: %s', self.current_client)

        # Finally, give the client focus if it should have it
        if client:
            if getfocus and self.focus_client != client:
                self.focus_client = client
                client.get_focus(time)

        # No client, reset focus
        else:
            self.display.set_input_focus(X.PointerRoot,
                                         X.RevertToPointerRoot, time)

    def rdb_get(self, res, cls, default = None):
        """rdb_get(res, cls, default = None)

        Get a value from the resource database.

        RES and CLS should omit the first component, and thus start
        with periods '.'.  This is because the application name
        (fetched from sys.argv[0]) will be prepended to RES,
        and self.appclass will be prepended to CLS.

        DEFAULT is returned if the resource can't be found.
        """

        return self.rdb.get(self.appname + res, self.appclass + cls, default)


    def system(self, cmd, fg = 0, evt = None, redirect = None):
        """Run CMD on the current screen.
        """
        return self.current_screen.system(cmd, fg = fg, evt = evt,
                                          redirect = redirect)

    def add_command_event(self, pid, evt):
        """Add PID to the list of child processes to wait for, inserting
        EVT in the event queue when it does.
        """
        self.child_events[pid] = evt

    def sigchld_handler(self, sig, frame):
        """Signal handler for SIGCHLD.
        """

        while 1:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break

                # child with event handler
                if self.child_events.has_key(pid):
                    evt = self.child_events[pid]
                    del self.child_events[pid]
                    evt.status = status
                    self.events.put_event(evt)

                # unmanaged child, we might be interested in it anyway
                # so record it.
                else:
                    self.children_exit_status.append((pid, status))

            except os.error, val:
                if val.errno == errno.EINTR:
                    continue
                if val.errno == errno.ECHILD:
                    break
                raise val


        # Call the old sigchld handler, if any
        if self.old_sigchld_handler:
            self.old_sigchld_handler(sig, frame)


    def fake_button_click(self, button):
        self.display.xtest_fake_input(X.ButtonPress, button, 0)
        self.display.xtest_fake_input(X.ButtonRelease, button, 5)
        self.display.flush()



    #
    # Cyclops circular reference detecting support
    #
    def _register_cycle_roots(self, cyclefinder):
        """Call this function after having initialised the
        WindowManager.  It will register all dynamically added objects,
        mainly Clients.  Then call loop or brave_loop with the run
        method of the cyclefinder object.
        """

        # Currently, the WindowManager has no dynamic objects,
        # only static ones like Screen.  So ask them.
        for s in self.screens:
            s._register_cycle_roots(cyclefinder)


    def _cleanup_cycle_roots(self):
        """Free all dynamically added objects.
        """

        # WindowManager only has this link to any Clients
        self.focus_client = None

        # But the screens have more...
        for s in self.screens:
            s._cleanup_cycle_roots()


def call_inits(cls, method, obj):
    """Call constructors for all mixin classes.

    If CLS has a method named METHOD, it will be called with OBJ as an argument.
    Otherwise call_inits will be called recursively for each base class of CLS.
    """

    if cls.__dict__.has_key(method):
        cls.__dict__[method](obj)
    else:
        for c in cls.__bases__:
            call_inits(c, method, obj)



class WindowProxyBase:
    """Base class for proxy objects for the real Xlib window objects.

    These proxies can override the Xlib window object methods when
    necessary.
    """

    def __init__(self, screen, window):
        self._screen = screen
        self._window = window
        self._wm = screen.wm

        # These Xlib casts allows the proxy object to be passed to any
        # Xlib method expecting one of the following objects
        self.__resource__ = window.__resource__
        self.__drawable__ = window.__resource__
        self.__window__ = window.__resource__

        # And these allows the proxy, for dictionary purposes, to
        # pretend to be the actual window object.
        self.__cmp__ = window.__cmp__
        self.__hash__ = window.__hash__


    def __proxy_event_init__(self, client):
        # Client can now register event handlers
        self._client = client


    def __getattr__(self, attr):
        # Unknown attribute in the proxy, grab it from the real window instead
        v = getattr(self._window, attr)

        # And avoid this getting called again for this attr
        setattr(self, attr, v)

        return v


    def _proxy_withdraw(self):
        """Called by Client when the proxied window is gone, to allow any cleanup.
        """
        pass
        

    def __str__(self):
        return '<%s for %s 0x%08x>' % (
            self.__class__, 
            self._window.__class__, self._window.id)


    def __repr__(self):
        return self.__str__()


# main function, parsing some common options and doing
# all that typical initialization.

wm_options = rdb.stdopts.copy()
wm_options['-debug'] =  rdb.SepArg('.debug')
wm_options['-version'] =  rdb.IsArg('.version')

def main(wmclass, extra_options = {}, xlib_version = required_xlib_version):
    global debug, debug_what

    # Check Xlib version
    if Xlib.__version__ < xlib_version:
        raise BadXlibVersion('requires Xlib %s, found %s'
                             % (string.join(map(str, xlib_version), '.'),
                                string.join(map(str, Xlib.__version__), '.')))

    opts = wm_options.copy()
    opts.update(extra_options)

    disp, name, db, args = rdb.get_display_opts(opts)

    # Print PLWM version, if set
    version = db.get(name + '.version', 'PLWM.Version', None)
    if version == '-version':
        try:
            sys.stderr.write('PLWM version: %s\n' % plwm.__version__)
        except AttributeError:
            sys.stderr.write('PLWM version: unknown (probably in build tree)\n')

    # Get debug info
    dbg = db.get(name + '.debug', 'PLWM.Debug', None)

    # Parse debugstring, separated by commas, and remove any whitespace and
    # empty elements
    if dbg is not None:
        dbg = string.split(dbg, ',')
        dbg = map(string.strip, dbg)
        dbg = filter(None, dbg)

        debug_what = dbg
        debug = do_debug

    try:
        wm = wmclass(disp, name, db)
    except NoUnmanagedScreensError:
        sys.stderr.write(sys.argv[0] + ': Another window manager already running?\n')
        sys.exit(1)

    try:
        wm.brave_loop()

    # Exit gracefully on Ctrl-C
    except KeyboardInterrupt:
        sys.exit(0)

