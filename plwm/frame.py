# frame.py - reparent client windows into a decorated frame
#
#    Copyright (C) 2008  Peter Liljenberg <peter.liljenberg@gmail.com>
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

from Xlib import X, Xutil, Xatom

import wmanager
import wmevents

class FrameProxy(wmanager.WindowProxyBase):

    # simple demo right now, but still a little configurable
    _frame_width = 2
    _title_font = 'fixed'
    _title_color = '#ffffff'
    _unfocused_color = '#444444'
    _focused_color = '#2244aa'
    _urgent_color = '#dd6622'

    _NET_WM_STATE = None
    _NET_WM_STATE_DEMANDS_ATTENTION = None

    def __init__(self, screen, window, *args, **keys):
        wmanager.WindowProxyBase.__init__(self, screen, window, *args, **keys)

        if FrameProxy._NET_WM_STATE is None:
            FrameProxy._NET_WM_STATE = self._wm.display.intern_atom("_NET_WM_STATE")
            FrameProxy._NET_WM_STATE_DEMANDS_ATTENTION = self._wm.display.intern_atom("_NET_WM_STATE_DEMANDS_ATTENTION")

        self._font = self._wm.get_font(self._title_font)
        self._title_pixel = self._screen.get_color(self._title_color)
        self._unfocused_pixel = self._screen.get_color(self._unfocused_color)
        self._focused_pixel = self._screen.get_color(self._focused_color)
        self._urgent_pixel = self._screen.get_color(self._urgent_color)

        fq = self._font.query()

        self._extra_height = fq.font_ascent + fq.font_descent + 3 * self._frame_width
        self._extra_width = 2 * self._frame_width

        self._title_x = self._frame_width
        self._title_y = self._frame_width
        self._title_base = self._frame_width + fq.font_ascent
        self._client_x = self._frame_width
        self._client_y = fq.font_ascent + fq.font_descent + 2 * self._frame_width
        self._focused = False


        # Create a proxy window for the frame that will contain the
        # real window

        g = window.get_geometry()

        self._frame = self._screen.root.create_window(
            g.x - self._client_x - g.border_width,
            g.y - self._client_y - g.border_width,
            g.width + self._extra_width,
            g.height + self._extra_height,
            0,
            X.CopyFromParent, X.InputOutput, X.CopyFromParent,
            background_pixel = self._unfocused_pixel,
            event_mask = X.ExposureMask | X.SubstructureRedirectMask
            )

        wmanager.debug('frame', 'created frame %s for client %s', self._frame, self._window)

        self._gc = self._frame.create_gc(
            foreground = self._title_pixel,
            font = self._font)

        # Reparent the real window into the frame window, blocking any
        # UnmapNotify that might generate

        screen.event_mask.block(X.SubstructureNotifyMask)
        window.configure(border_width = 0)
        window.reparent(self._frame, self._client_x, self._client_y)
        screen.event_mask.unblock(X.SubstructureNotifyMask)


        # Some methods can be overridden simply by only working on the proxy window
        self.get_geometry = self._frame.get_geometry
        self.circulate = self._frame.circulate
        self.reparent = self._frame.reparent

        self._screen.add_proxy_window(self._frame, window)


    def __proxy_event_init__(self, client, *args, **keys):
        wmanager.WindowProxyBase.__proxy_event_init__(self, client, *args, **keys)

        # Register event handlers now that the client is set up.
        # Don't set any event masks, we did that already when creating
        # the frame window
        client.dispatch.add_handler(X.Expose, self._expose, masks = ())

        client.dispatch.add_handler(wmevents.ClientFocusIn, self._focus_in)
        client.dispatch.add_handler(wmevents.ClientFocusOut, self._focus_out)

        client.dispatch.add_handler(X.PropertyNotify, self._property_notify)


    def _proxy_withdraw(self):
        # Move window back to be an immediate child of root
        g = self._frame.get_geometry()

        self._frame.change_attributes(event_mask = 0)

        self._window.reparent(self._screen.root,
                              g.x + self._client_x,
                              g.y + self._client_y)

        self._screen.remove_proxy_window(self._frame)
        self._frame.destroy()


    def _expose(self, e):
        # Trivial exposure handling: redraw everything on final expose event
        if e.count == 0:
            self._redraw()


    def _focus_in(self, e):
        self._frame.change_attributes(background_pixel = self._focused_pixel)
        self._focused = True
        self._redraw()


    def _focus_out(self, e):
        self._frame.change_attributes(background_pixel = self._unfocused_pixel)
        self._focused = False
        self._redraw()


    def _property_notify(self, evt):
        if evt.atom == Xatom.WM_NAME:
            self._redraw()
        if evt.atom == Xatom.WM_HINTS:
            wmh = self._window.get_wm_hints()
            if wmh and wmh.flags & Xutil.UrgencyHint:
                self._frame.change_attributes(background_pixel = self._urgent_pixel)
            else:
                if self._focused:
                    self._frame.change_attributes(background_pixel = self._focused_pixel)
                else:
                    self._frame.change_attributes(background_pixel = self._unfocused_pixel)
        elif evt.atom == FrameProxy._NET_WM_STATE:
            demands_attention = self._window.get_property(FrameProxy._NET_WM_STATE, Xatom.WINDOW, 0, 1)
            if demands_attention is not None and demands_attention.value[0] == FrameProxy._NET_WM_STATE_DEMANDS_ATTENTION:
                self._frame.change_attributes(background_pixel = self._urgent_pixel)
            else:
                if self._focused:
                    self._frame.change_attributes(background_pixel = self._focused_pixel)
                else:
                    self._frame.change_attributes(background_pixel = self._unfocused_pixel)
            self._redraw()


    def _redraw(self):
        wmanager.debug('frame', 'redrawing')
        self._frame.clear_area()

        # Don't draw text in frame border
        g = self._frame.get_geometry()

        self._gc.set_clip_rectangles(
            0, 0, [(self._frame_width,
                    self._frame_width,
                    g.width - self._extra_width,
                    g.height - self._extra_height)],
            X.YXBanded)

        self._frame.draw_text(self._gc, self._title_x, self._title_base,
                              self._client.get_title())
                    
        self._gc.change(clip_mask = X.NONE)


    # Override the necessary window methods

    def destroy(self, onerror = None):
        self._window.destroy()
        self._frame.destroy()
        

    def map(self, onerror = None):
        # Map both windows, so that the real window gets a MapNotify
        self._window.map()
        self._frame.map()


    def unmap(self, onerror = None):
        # Ditto but reverse
        self._frame.unmap()
        self._window.unmap()


    def configure(self, onerror = None, **keys):
        # Resize in lockstep, but otherwise all configuration is made
        # on the proxy

        real_keys = {}
        if 'width' in keys:
            real_keys['width'] = keys['width'] - self._extra_width
            
        if 'height' in keys:
            real_keys['height'] = keys['height'] - self._extra_height

        self._frame.configure(onerror = onerror, **keys)
        
        if real_keys:
            self._window.configure(onerror = onerror, **real_keys)


    def get_wm_normal_hints(self):
        # Must add in the frame to the size hints
        hints = self._window.get_wm_normal_hints()
        
        if hints:
            hints.min_width = hints.min_width + self._extra_width
            hints.min_height = hints.min_height + self._extra_height

            if hints.max_width:
                hints.max_width = hints.max_width + self._extra_width

            if hints.max_height:
                hints.max_height = hints.max_height + self._extra_height

            if hints.flags & Xutil.PBaseSize:
                hints.base_width = hints.base_width + self._extra_width
                hints.base_height = hints.base_height + self._extra_height
                
        return hints


    def __str__(self):
        return '<%s 0x%08x for %s 0x%08x>' % (
            self.__class__, self._frame.id,
            self._window.__class__, self._window.id)

    def __repr__(self):
        return self.__str__()


