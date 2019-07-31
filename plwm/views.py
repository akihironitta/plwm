#
# views.py -- Handle views ("workspaces")
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


from Xlib import X, Xatom
import types
import time
import modewindow
import string
import cfilter
import wmanager
import wmevents

class ViewedClient:
    def __client_init__(self):
        if not self.view_create_latent(self):
            self.start_iconified = 1

# screen mixin
class ViewHandler:
    view_always_visible_clients = cfilter.false

    # If true, views will be reorded with the most-recently visited at
    # the front.  This means that finding a view when several match
    # the last visited view will be found first, rather than the one
    # that happens to follow the currently visited view.
    view_reorder_views = 0

    # How long a view must have been current to be deemed visited, in
    # seconds.  Must be > 0, otherwise only the last visited view can
    # be reached.
    view_reorder_delay = 2.0


    def __screen_client_init__(self):
        if self.view_reorder_views and self.view_reorder_delay <= 0:
            raise ValueError('view_reorder_delay must be > 0: %f' % self.view_reorder_delay)

        self.PLWM_VIEW_LIST = self.wm.display.intern_atom('_PLWM_VIEW_LIST')
        self.PLWM_VIEW_WINCONF = self.wm.display.intern_atom('_PLWM_VIEW_WINCONF')

        self.view_winconf = None
        self.view_latent_clients = {}
        self.view_visible_clients = []
        self.view_clear_all()

    def __screen_init__(self):
        self.view_fetch()

        self.wm.dispatch.add_handler(wmevents.QuitWindowManager,
                                     self.view_handle_quit)


    def view_handle_quit(self, evt):
        # Store configuration when plwm exits
        if self.view_current:
            self.view_leave()
        self.view_store()

    def view_clear_all(self):
        self.view_next_id = 0
        v = View(self, self.view_get_next_id())
        self.view_list = [v]
        self.view_current = v
        self.view_index = 0
        self.view_enter_time = time.time()
        self.view_enter_method = None

    def view_get_next_id(self):
        """Return the next unique view identifier.
        """
        self.view_next_id = self.view_next_id + 1
        return self.view_next_id


    def view_store(self):
        """Store PLWM_VIEW_LIST property on root window.
        This does not store properties for each view, that is
        done by View.leave.

        The data is an 32-bit array of integers.  data[0] is the index
        of the current view in the list of views.  data[1:] is the view
        ids.
        """

        va = [self.view_index]
        for v in self.view_list:
            va.append(v.id)
        self.root.change_property(self.PLWM_VIEW_LIST, self.PLWM_VIEW_LIST, 32, va)

    def view_fetch(self):
        """Read the PLWM_VIEW* properties to replicate that view set.

        Returns true if the views were successfully read, false otherwise.
        """
        # First fetch the current view index
        f = self.root.get_full_property(self.PLWM_VIEW_LIST, self.PLWM_VIEW_LIST)
        if not f or f.format != 32 or not f.value:
            return 0

        index = int(f.value[0])

        # Build the view list
        self.view_list = []
        for d in map(int, f.value[1:]):
            if d > self.view_next_id:
                self.view_next_id = d
            v = View(self, d)
            v.fetch_winconf()
            v.fetch_tags()
            self.view_list.append(v)

        self.view_index = index
        self.view_current = self.view_list[self.view_index]
        self.view_enter()
        return 1

    def view_current_index(self):
        return self.view_index

    def view_create(self, clientdefs, latent = 0):
        """Create a new veiw, but doesn't go to it.

        CLIENTDEFS is a list of clients to view initially.  Each element should
        be either a client name or a tuple of one or more fields:

        (name, geometry, grab)

        If LATENT if false, the view will not be created unless at least one
        specified client exists.
        If LATENT is true, the view will be created when a matching client is
        created.

        Returns the new view number, or None if a latent view isn't created
        immediately.
        """
        clients = []
        defs = {}
        anymapped = 0
        for cdef in clientdefs:
            name = cdef
            geometry = None
            grab = None
            try:
                name = cdef[0]
                geometry = cdef[1]
                grab = cdef[2]
            except IndexError:
                pass

            defs[name] = (geometry, grab)

            for c in self.clients.values():
                if name == c.res_name or name == c.res_class:
                    clients.append((c, geometry, grab))
                    if c.is_mapped():
                        anymapped = 1

        # Named clients exists, so create a view now
        if anymapped:
            v = View(self, self.get_next_view_id())
            self.view_list.append(v)
            for c, geometry, grab in clients:
                v.donate_client(c, geometry)
                if grab:
                    c.iconify()

            return len(self.view_list) - 1

        elif latent:
            self.view_latent_clients.update(defs)
            return None

        else:
            return None

    def view_create_latent(self, client):
        """Create a latent view if it waits for CLIENT.

        Return true if this client should be mapped now,
        false otherwise.
        """

        found = 0
        if self.view_latent_clients.has_key(client.res_class):
            geometry, grab = self.view_latent_clients[client.res_class]
            del self.view_latent_clients[client.res_class]
            found = 1

        if self.view_latent_clients.has_key(client.res_name):
            geometry, grab = self.view_latent_clients[client.res_name]
            del self.view_latent_clients[client.res_name]
            found = 1

        name = client.fetch_name()
        if self.view_latent_clients.has_key(name):
            geometry, grab = self.view_latent_clients[name]
            del self.view_latent_clients[name]
            found = 1

        if not found:
            return 1

        v = View(self, self.get_next_view_id())
        self.view_list.append(v)
        v.donate_client(client, geometry)

        return not grab


    def view_goto(self, index, noexc = 0):
        """Display the view index by INDEX.

        If NOEXC is not passed or is false an IndexError exception will
        be raised if the view doesn't exist.
        If NOEXC is true nothing will happen if the view doesn't exist.
        """
        if index != self.view_index:
            if noexc and len(self.view_list) <= index:
                return

            v = self.view_list[index]
            self.view_index = index
            self.view_leave()
            self.view_enter()

    def view_find_with_client(self, clients):
        """Display the next view with a client matching the
        filter CLIENTS.
        """
        def view_has_client(view, clients):
            for winconf in view.winconf:
                if winconf.mapped and clients(winconf.client):
                    return 1
            return 0

        self.view_reorder_before_move('find %s' % str(clients))

        for i in range(self.view_index + 1, len(self.view_list)):
            if view_has_client(self.view_list[i], clients):
                self.view_goto(i)
                return
        for i in range(0, self.view_index):
            if view_has_client(self.view_list[i], clients):
                self.view_goto(i)
                return

        if not view_has_client(self.view_current, clients):
            self.wm.display.bell(0)

    def view_next(self):
        """Display the next view.
        """
        if len(self.view_list) > 1:
            self.view_reorder_before_move('prevnext')
            self.view_index = (self.view_index + 1) % len(self.view_list)
            self.view_leave()
            self.view_enter()

    def view_prev(self):
        """Display the previous view.
        """
        if len(self.view_list) > 1:
            self.view_reorder_before_move('prevnext')
            self.view_index = (self.view_index - 1) % len(self.view_list)
            self.view_leave()
            self.view_enter()

    def view_new(self, copyconf = 0):
        """Create a new view after the current.

        If COPYCONF is not passed or is false, the new View will be empty,
        otherwise it will be a copy of the current view.
        """

        self.view_reorder_before_move('new')

        self.view_index = self.view_index + 1
        self.view_list.insert(self.view_index,
                          View(self, self.view_get_next_id()))
        self.view_leave()
        if copyconf:
            self.view_current.winconf = self.view_winconf
        self.view_enter()

    def view_tag(self, tag):
        """Set or remove TAG from the current view.
        """

        self.view_current.tag(tag)

    def view_find_tag(self, tag):
        """Goto the next view tagged with TAG.
        """

        self.view_reorder_before_move('tag %s' % tag)

        for i in range(self.view_index + 1, len(self.view_list)):
            if self.view_list[i].has_tag(tag):
                self.view_goto(i)
                return
        for i in range(0, self.view_index):
            if self.view_list[i].has_tag(tag):
                self.view_goto(i)
                return

        if not self.view_current.has_tag(tag):
            self.wm.display.bell(0)

    def view_leave(self):
        """Internal function for ViewHandler objects.

        Call after setting self.view_index to the new view, but with
        self.current still pointing to the old view.

        self.current will point to the new view when this functions
        is finished.
        """

        winconf, empty = self.view_current.leave()

        if empty:
            old_index = self.view_list.index(self.view_current)

            # Delete this view as it has become empty
            del self.view_list[old_index]

            # And adjust the destination index, if it was after the now deleted view
            if self.view_index > old_index:
                self.view_index -= 1

        try:
            self.view_current = self.view_list[self.view_index]
        except IndexError:
            self.view_current = self.view_list[0]
            self.view_index = 0

        self.view_winconf = winconf

        # Store views as a property
        self.view_store()

    def view_enter(self):
        """Internal function for ViewHandler objects.

        Call after view_leave() to reconfigure the windows.
        """
        if self.view_winconf:
            self.view_current.enter(self.view_winconf)

        self.view_enter_time = time.time()


    def view_reorder_before_move(self, method):
        """Internal function.

        Moves this view to the front of the list, if reorder is
        enabled and the view has been visible for long enough.  Also
        move if the enter method differs from the previous move type.

        Call this in any view changing methods that steps or searches
        among views, to get the go-to-most-recently-visited
        functionality.
        """

        if not self.view_reorder_views:
            return

        wmanager.debug('view', 'reordering, method %s', method)
        old_method = self.view_enter_method
        self.view_enter_method = method

        if self.view_index == 0:
            return

        now = time.time()
        if (now - self.view_enter_time >= self.view_reorder_delay
            or old_method != method):

            wmanager.debug('view', 'reordering, moving view %d from index %d to front',
                           self.view_current.id, self.view_list.index(self.view_current))

            self.view_list.remove(self.view_current)
            self.view_list.insert(0, self.view_current)
            self.view_index = 0


class XMW_ViewHandler(ViewHandler):
    def __screen_client_init__(self):
        ViewHandler.__screen_client_init__(self)
        self.view_xmw_count_message = modewindow.Message(.9, modewindow.LEFT)
        self.modewindow_add_message(self.view_xmw_count_message)

    def view_enter(self):
        ViewHandler.view_enter(self)
        self.view_xmw_update()

    def view_tag(self, tag):
        ViewHandler.view_tag(self, tag)
        self.view_xmw_update()

    def view_xmw_update(self):
        text = '%d/%d' % (self.view_index + 1, len(self.view_list))

        tags = self.view_current.get_tags()
        if tags:
            text = text + ' (' + string.join(tags, ', ') + ')'

        self.view_xmw_count_message.set_text(text)


WINCONF_CLIENT = 0
WINCONF_PTRPOS = 1
WINCONF_FOCUS_CLIENT = 2

class WinConf:
    def __init__(self, client, x, y, width, height, mapped):
        self.client = client
        self.x = max(x, 0) # change_property breaks on negative...
        self.y = max(y, 0)
        self.width = width
        self.height = height
        self.mapped = mapped

    def get_tuple(self):
        """Return a tuple encoding this winconf.
        """
        return (self.client.window.__window__(), self.x, self.y,
                self.width, self.height, self.mapped)

class View:
    def __init__(self, screen, viewid):
        self.screen = screen
        self.wm = screen.wm
        self.id = viewid
        self.tags = []
        self.WINCONF = self.wm.display.intern_atom('_PLWM_VIEW_WINCONF_U%d'
                                                   % self.id)
        self.TAGS = self.wm.display.intern_atom('_PLWM_VIEW_TAGS_U%d'
                                                % self.id)

        # A winconf is a list of WinConfs
        # in stacking order, bottommost first.
        self.winconf = []

        # Keep track of where the pointer is when we leave this view
        self.ptrx = None
        self.ptry = None

        # Keep track of the focused client
        self.focus_client = None

    def store_winconf(self):
        """Store the winconf for this view.  The format is a
        32 bit list where each winconf is sequentially stored.
        """
        wca = ()

        # Encode winconfs
        for w in self.winconf:
            t = w.get_tuple()
            wca = wca + (WINCONF_CLIENT, len(t)) + t

        # Encode pointer position
        if self.ptrx is not None and self.ptry is not None:
            wca = wca + (WINCONF_PTRPOS, 2, self.ptrx, self.ptry)

        # Encode focused client
        if self.focus_client:
            wca = wca + (WINCONF_FOCUS_CLIENT, 1, self.focus_client.window.id)

        # Store the view configuration
        self.screen.root.change_property(self.WINCONF, self.screen.PLWM_VIEW_WINCONF,
                                         32, wca)

    def fetch_winconf(self):
        """Fetch the winconf property for this view.
        """

        # Fetch the first bytes
        f = self.screen.root.get_full_property(self.WINCONF,
                                               self.screen.PLWM_VIEW_WINCONF,
                                               40)

        if not f or f.format != 32 or not f.value:
            return

        data = map(int, f.value)

        while len(data) >= 2:
            # Fetch the type of configuration and length
            wt = data[0]
            wl = data[1]

            # Abort if there isn't enough data left
            if wl > len(data) - 2:
                break

            # Extract config data and remove the used part
            wd = data[2 : wl + 2]
            del data[0 : wl + 2]

            if wt == WINCONF_PTRPOS:
                if wl >= 2:
                    self.ptrx, self.ptry = wd[:2]

            elif wt == WINCONF_CLIENT:
                # Read the length of winconf item, minimum 6
                # and we ignore everything above 6
                if wl >= 6:
                    win = self.wm.display.create_resource_object('window', wd[0])
                    c = self.screen.get_client(win)
                    if c:
                        self.winconf.append(apply(WinConf, (c,) + tuple(wd[1:6])))
            elif wt == WINCONF_FOCUS_CLIENT:
                if wl >= 1:
                    window = self.wm.display.create_resource_object('window', wd[0])
                    self.focus_client = self.screen.get_client(window)


    def store_tags(self):
        """Store the tags property for this view.
        """

        if self.tags:
            self.screen.root.change_property(self.TAGS, Xatom.STRING,
                                             8, string.join(self.tags, '\0'))
        else:
            self.screen.root.delete_property(self.TAGS)


    def fetch_tags(self):
        """Fetch the tags property for this view.
        """
        # Fetch the first bytes
        f = self.screen.root.get_full_property(self.TAGS, Xatom.STRING)

        if not f or f.format != 8:
            return

        self.tags = string.split(f.value, '\0')

    def leave(self):
        """Notify the View that it is being unviewed.

        Return a tuple: (winconf, empty).
        WINCONF is the View's winconf.
        EMPTY is true if there are no visible windows left.
        """
        empty = 1

        # Find all the current windows
        clients = self.screen.query_clients(stackorder = 1)
        self.winconf = []
        for c in clients:
            x, y, w, h = c.geometry()[0:4]
            self.winconf.append(WinConf(c, x, y, w, h, c.is_mapped()))

            if c.is_mapped() \
               and not self.screen.view_always_visible_clients(c):
                empty = 0

        # Find the pointer positon
        r = self.screen.root.query_pointer()
        if r.same_screen:
            self.ptrx = r.win_x
            self.ptry = r.win_y
        else:
            self.ptrx = self.ptry = None

        # Find the focused client
        if self.wm.focus_client and self.wm.focus_client.screen == self.screen:
            self.focus_client = self.wm.focus_client
        else:
            self.focus_client = None

        # Store winconf as property
        if not empty:
            self.store_winconf()
        # Or delete it if we're empty
        else:
            self.screen.root.delete_property(self.WINCONF)
            self.screen.root.delete_property(self.TAGS)

        return self.winconf, empty

    def enter(self, winconf):
        """Enter a View.

        The View gets the last View's WINCONF and shall install
        its own.
        """

        # Unmap unwanted but mapped clients
        mapc = {}
        for w in self.winconf:
            mapc[w.client] = w.mapped
        for w in winconf:
            if not mapc.get(w.client, 0) and not self.screen.view_always_visible_clients(w.client):
                w.client.iconify()

        # Move the pointer, if that has been stored previously
        if self.ptrx is not None and self.ptry is not None:
            self.screen.root.warp_pointer(self.ptrx, self.ptry)

        # Reconfigure all clients, and map the visible ones
        deicon = []
        for w in self.winconf:
            # Configure window, delayed if iconified
            w.client.moveresize(w.x, w.y, w.width, w.height, 1)
            w.client.raisewindow()
            if w.mapped:
                deicon.append(w.client)

        deicon.reverse()
        for c in deicon:
            c.deiconify()

        # Refocus if applicable
        if self.focus_client:
            self.wm.set_current_client(self.focus_client, X.CurrentTime)

    def donate_client(self, client, geometry):
        """Donate a client to this view.
        """

        ### FIXME:  actually use geometry argument
        x, y, w, h = client.geometry()[0:4]
        self.winconf.append(WinConf(client, x, y, w, h, 1))


    def tag(self, tag):
        """Set or remove TAG from this view.
        """
        if tag in self.tags:
            self.tags.remove(tag)
        else:
            self.tags.append(tag)
        self.store_tags()

    def has_tag(self, tag):
        """Return true if this view is tagged with TAG.
        """
        return tag in self.tags

    def get_tags(self):
        """Return all tags on this view.
        """
        return self.tags
