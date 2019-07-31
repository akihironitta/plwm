# composite.py - interface plcm to produce visual effects
#
#    Copyright (C) 2007  Peter Liljenberg <peter.liljenberg@gmail.com>
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

"""

plwm.composite supports plcm (the pointless composition manager) in
manipulating the display of client window contents.

This is done by reparenting each client window into a proxy window.
plcm can then be told to render the client window into this proxy
window allowing for effects as dimming the brightness, reversing
brightness, or zooming.

The WindowManager mixin CompositeManager handles some of the
communication with plcm.
"""

import struct

from Xlib import X, Xatom, error
import Xlib.protocol.event
from Xlib.ext.composite import RedirectManual

import wmanager

class ClientSettings:
    def __init__(self):
        # -255 to +255
        self.brightness = 0

        # Ratio, None == 1.0
        self.zoom = None

    def no_effects(self):
        """Return true if these settings means that no effects will be
        performed by plcm.
        """

        return self.brightness == 0 and self.zoom is None


class CompositionManager:
    """WindowManager mixin, providing an interface to plcm.
    """

    def __wm_screen_init__(self):
        self.comp_control_window = None

        # Map of clients managed by plcm to the current settings
        self.comp_clients = {}

        # The plcm interface atoms
        self._PLCM_CONTROL_WINDOW = self.display.intern_atom('_PLCM_CONTROL_WINDOW')
        self._PLCM_ENABLE = self.display.intern_atom('_PLCM_ENABLE')
        self._PLCM_DISABLE = self.display.intern_atom('_PLCM_DISABLE')
        self._PLCM_BRIGHTNESS = self.display.intern_atom('_PLCM_BRIGHTNESS')


    def comp_set_brightness(self, client, value):
        """Set the brightness of CLIENT to VALUE.

        Range of VALUE is -255 (black) to +255 (white).  Set to 0 to
        disable any brightness adjustment.
        """

        value = int(value)

        if value < -255 or value > 255:
            raise ValueError('brightness %s out of range' % value)
        
        try:
            settings = self.comp_clients[client]

            # Noop, no point in doing anything
            if settings.brightness == value:
                return
            new_client = 0

        except KeyError:
            # No adjustment for new client?  No need to do anything, then
            if value == 0:
                return
            
            settings = ClientSettings()
            new_client = 1

        self.comp_do_set_brightness(client, settings, value)

        if new_client:
            self.comp_enable_client(client, settings)
        

    def comp_change_brightness(self, client, change):
        """Change the brightness of CLIENT by CHANGE (negative means
        darker, positive means brighter.
        """

        change = int(change)
        if change == 0:
            return
        
        try:
            settings = self.comp_clients[client]
            new_client = 0
        except KeyError:
            settings = ClientSettings()
            new_client = 1

        new_value = max(-255, min(settings.brightness + change, 255))

        # Already maxed out?
        if new_value == settings.brightness:
            return
        
        self.comp_do_set_brightness(client, settings, new_value)

        if new_client:
            self.comp_enable_client(client, settings)
            

    def comp_enable_client(self, client, settings = None):
        """Explicitly enable composition effects for CLIENT.

        Normally, this is done by calling
        e.g. comp_change_brightness().
        """

        # Is client already composition enabled?
        if client in self.comp_clients:
            return

        # Is composition disabled due to strange visuals?
        if client.window._composition_disabled:
            wmanager.debug('composite', 'composition disabled for client %s', client)
            return

        # When render redirection is enabled for the client, it will
        # be unmapped and then remapped. Block those events so they
        # aren't misinterpreted as a withdrawal.

        # This is an disadvantage of splitting the main work of
        # composition into plcm: it would be much more natural for
        # plcm to handle everything there is about composition, but it
        # is nigh on impossible to reliably block plwm from receiving
        # these events then.

        client.window._proxy.change_attributes(event_mask = X.NoEventMask)
        client.event_mask.block(X.StructureNotifyMask)
        client.window._window.composite_redirect_window(RedirectManual)
        client.event_mask.unblock(X.StructureNotifyMask)
        client.window._proxy.change_attributes(event_mask = X.SubstructureRedirectMask)

        if self.comp_send_plcm_message(
            self._PLCM_ENABLE,
            client.window._window,
            client.window._proxy):
        
            wmanager.debug('composite', 'enabled composition for client %s', client)

            if settings is None:
                settings = ClientSettings()

            self.comp_clients[client] = settings
        else:
            self.comp_remove_redirection(client)
            

    def comp_disable_client(self, client):
        """Explicitly disable composition effects for CLIENT.

        Normally, this is done by calling
        e.g. comp_set_brightness() with value 0.
        """

        # Is client composition enabled?
        if client not in self.comp_clients:
            return
        
        self.comp_send_plcm_message(
            self._PLCM_DISABLE,
            client.window._window,
            client.window._proxy)
        
        wmanager.debug('composite', 'disabled composition for client %s', client)

        del self.comp_clients[client]
        self.comp_remove_redirection(client)


    #
    # Internal methods
    #
    
    def comp_do_set_brightness(self, client, settings, value):
        wmanager.debug('composite', 'changing brightness from %d to %d for %s',
                       settings.brightness, value, client)

        settings.brightness = value

        if value != 0:

            # value must be unsigned
            if value < 0:
                value = struct.unpack('=L', struct.pack('=l', value))[0]

            client.window._proxy.change_property(
                self._PLCM_BRIGHTNESS, Xatom.INTEGER, 32, [value])
        else:
            client.window._proxy.delete_property(self._PLCM_BRIGHTNESS)

        # No longer any settings in effect?
        if settings.no_effects():
            self.comp_disable_client(client)


    def comp_remove_redirection(self, client):
        # See comment in comp_enable_client
        client.window._proxy.change_attributes(event_mask = X.NoEventMask)
        client.event_mask.block(X.StructureNotifyMask)
        client.window._window.composite_unredirect_window(RedirectManual)
        client.event_mask.unblock(X.StructureNotifyMask)
        client.window._proxy.change_attributes(event_mask = X.SubstructureRedirectMask)

        client.window._proxy.delete_property(self._PLCM_BRIGHTNESS)
        

    def comp_send_plcm_message(self, message, source, target):
        if self.comp_control_window is None:
            # Try to find the control window on demand, instead of
            # being fancy and waiting for events about it

            root = self.display.screen(0).root

            r = root.get_full_property(self._PLCM_CONTROL_WINDOW, Xatom.WINDOW)
            if r is None or r.format != 32 or len(r.value) != 1:
                wmanager.debug('composite', 'no plcm control window, not doing anything')
                return 0

            self.comp_control_window = self.display.create_resource_object(
                'window', r.value[0])

            wmanager.debug('composite', 'plcm control window: %s',
                           self.comp_control_window)
            
        # We knows the ID of the control window now

        ev = Xlib.protocol.event.ClientMessage(
            window = self.comp_control_window,
            client_type = message,
            data = (32, [source.id, target.id, 0, 0, 0]))

        self.comp_control_window.send_event(ev, onerror = self.comp_send_message_error)
        return 1


    def comp_send_message_error(self, error, request):
        wmanager.debug('composite', 'error when sending message to plcm: %s', error)
        wmanager.debug('composite', 'disabling all enabled clients')
        
        for client in self.comp_clients.iterkeys():
            self.comp_remove_redirection(client)

        self.comp_clients = {}
        self.comp_control_window = None

        
class CompositeProxy(wmanager.WindowProxyBase):
    def __init__(self, screen, window, *args, **keys):
        wmanager.WindowProxyBase.__init__(self, screen, window, *args, **keys)

        # Create a proxy window that will contain the real window as a
        # clone of the source window.

        g = window.get_geometry()
        a = window.get_attributes()

        # Never trust an X server.  The visual and depth as returned
        # by the methods just called can result in a BadMatch, despite
        # the reasonable assumption that if the client could create a
        # window with those specs, then we can also do it.

        # The reason for this sad state of affairs is OpenGL: a GLX
        # visual that have 24 bits of colour info _and_ 8 bits of
        # alpha info appears to a non-GL application (e.g. plwm) to
        # have depth 24, but you can't create windows of that depth on
        # it.  An example of an application that does this is
        # OpenOffice 2.0, which is how I found it.

        # In this case, just create a window on the default visual for
        # the proxy and disable composition for this client (as plcm
        # require that the proxy and the client windows use the same
        # visual).

        self._composition_disabled = 0

        ec = error.CatchError(error.BadMatch)
        self._proxy = screen.root.create_window(
            g.x, g.y, g.width, g.height, g.border_width, g.depth,
            a.win_class, a.visual, onerror = ec)

        # Check if the mismatch was triggered
        self._wm.display.sync()

        if ec.get_error():
            wmanager.debug('composite', 'strange visual, disabling composition for %s', window)
            
            self._composition_disabled = 1
            self._proxy = screen.root.create_window(
                g.x, g.y, g.width, g.height, g.border_width, X.CopyFromParent)
            
            
        # The proxy window must have the SubstructureRedirectMask set, so
        # we still get MapRequest, ConfigureRequest etc for the client window.
        self._proxy.change_attributes(event_mask = X.SubstructureRedirectMask)

        # Reparent the real window into the proxy window, blocking any
        # UnmapNotify that might generate

        screen.event_mask.block(X.SubstructureNotifyMask)
        window.configure(border_width = 0)
        window.reparent(self._proxy, 0, 0)
        screen.event_mask.unblock(X.SubstructureNotifyMask)


        # Some methods can be overridden simply by only working on the proxy window
        self.get_geometry = self._proxy.get_geometry
        self.circulate = self._proxy.circulate
        self.reparent = self._proxy.reparent

        self._screen.add_proxy_window(self._proxy, window)


    def _proxy_withdraw(self):
        # Move window back to be an immediate child of root
        g = self._proxy.get_geometry()

        self._proxy.change_attributes(event_mask = 0)

        self._window.configure(border_width = g.border_width)
        self._window.reparent(self._screen.root, g.x, g.y)

        self._screen.remove_proxy_window(self._proxy)
        self._proxy.destroy()


    # Override those methods that must do more to get control over the
    # source window

    def change_attributes(self, onerror = None, **keys):
        # These two attrs should be set on the proxy, the
        # others on the real window

        proxy_keys = {}
        if 'border_pixmap' in keys:
            proxy_keys['border_pixmap'] = keys['border_pixmap']
            del keys['border_pixmap']

        if 'border_pixel' in keys:
            proxy_keys['border_pixel'] = keys['border_pixel']
            del keys['border_pixel']

        if proxy_keys:
            self._proxy.change_attributes(onerror = onerror, **proxy_keys)

        self._window.change_attributes(onerror = onerror, **keys)


    def destroy(self, onerror = None):
        self._window.destroy()
        self._proxy.destroy()
        

    def map(self, onerror = None):
        # Map both windows, so that the real window gets a MapNotify
        self._window.map()
        self._proxy.map()


    def unmap(self, onerror = None):
        # Ditto but reverse
        self._proxy.unmap()
        self._window.unmap()


    def configure(self, onerror = None, **keys):
        # Resize in lockstep, but otherwise all configuration is made
        # on the proxy

        real_keys = {}
        if 'width' in keys:
            real_keys['width'] = keys['width']
            
        if 'height' in keys:
            real_keys['height'] = keys['height']

        self._proxy.configure(onerror = onerror, **keys)
        
        if real_keys:
            self._window.configure(onerror = onerror, **real_keys)


    # For zoom:
    # def get_wm_normal_hints(self):


    def __str__(self):
        return '<%s 0x%08x for %s 0x%08x>' % (
            self.__class__, self._proxy.id,
            self._window.__class__, self._window.id)

    def __repr__(self):
        return self.__str__()


