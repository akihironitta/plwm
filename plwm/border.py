#
# border.py -- change border color on focused client
#
#    Copyright (C) 1999-2001,2006  Peter Liljenberg <petli@ctrl-c.liu.se>
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
import wmanager, wmevents, cfilter

class BorderClient:
    """Client mixin class managing a simple window border.

    The border has a width defined by the attribute
    border_default_width.  The attribute no_border_clients is a client
    filter that causes matching clients to have no border at all.

    The color of the border is managed by objects of some
    BorderColorManager subclass.  border_colors is a list of tuples
    (filter, manager).  When a new client is created the list is
    processed from the beginning and clients matching filter will have
    their border colors managed by the manager object.  If no filter
    matches the manager border_default_color is used instead.
    """

    no_border_clients = cfilter.false
    border_default_width = 3

    border_colors = ()
    border_default_color = None

    # These two attributes are for backward compatability, and are
    # equivalent to this:
    # border_default_color = FixedBorderColor(border_color_name,
    #                                         border_focuscolor_name)
    border_color_name = None
    border_focuscolor_name = None

    def __client_init__(self):
        self.border_color = None
        self.border_focuscolor = None

        if self.no_border_clients(self):
            self.setborderwidth(0)

        else:
            self.setborderwidth(self.border_default_width)

            manager = None
            for f, m in self.border_colors:
                if f(self):
                    manager = m
                    break
            else:
                manager = self.border_default_color

            if manager is None:
                # Use old color attributes
                manager = FixedBorderColor(self.border_color_name,
                                           self.border_focuscolor_name)

            manager.set_client_border_colors(self)

            # Set up dispatchers for the colors
            self.dispatch.add_handler(wmevents.ClientFocusIn, self.border_get_focus)
            self.dispatch.add_handler(wmevents.ClientFocusOut, self.border_lose_focus)


    def border_set_colors(self, blurred, focused):
        """This method should be called by the BorderColor object to
        set the border colors of the client, but might be called by
        other mixins too

        blurred and focused are the pixel values to be used for
        non-focused and focused clients, respectively.
        """

        self.border_color = blurred
        self.border_focuscolor = focused

        if self.focused:
            if self.border_focuscolor is not None:
                self.window.change_attributes(border_pixel = self.border_focuscolor)
        else:
            if self.border_color is not None:
                self.window.change_attributes(border_pixel = self.border_color)

    #
    # Event handlers
    #

    def border_get_focus(self, event):
        if self.border_focuscolor is not None:
            self.window.change_attributes(border_pixel = self.border_focuscolor)

    def border_lose_focus(self, event):
        if self.border_color is not None:
            self.window.change_attributes(border_pixel = self.border_color)


class BorderColorManager:
    """Base class for border color manager objects.

    It should be subclassed by actual managers, which must implement
    the set_client_border_colors() method.
    """

    def set_client_border_colors(self, client):
        """Override this to implement the border color selection for client.
        """
        raise NotImplementedError('%s.set_client_border_colors()' % self.__class__)


class FixedBorderColor(BorderColorManager):
    """Use fixed border colors, one for non-focused and one for focused clients.
    """

    def __init__(self, blurred, focused):
        """Set the color of all clients to blurred and focused, resp.

        They can either be strings naming a color, or three-tuples
        specifying a color as an (r, g, b) value in the range [0, 65535].
        """
        self.blurred_color = blurred
        self.focused_color = focused

    def set_client_border_colors(self, client):
        # The rdb stuff should be removed, but maybe someone is still using it...

        resname = client.wm.rdb_get('.border.color', '.Border.Color', '#000000')
        if self.blurred_color is not None:
            blurred = client.screen.get_color(self.blurred_color, default = resname)
        else:
            blurred = client.screen.get_color(resname)

        resname = client.wm.rdb_get('.border.focus.color',
                                    '.Border.Focus.Color', '#000000')
        if self.focused_color is not None:
            focused = client.screen.get_color(self.focused_color, default = resname)
        else:
            focused = client.screen.get_color(resname)

        client.border_set_colors(blurred, focused)


class TitleBorderColor(BorderColorManager):
    """Change the color of the border based on the client title.

    The hue will be the same for a client (as long as the title
    doesn't change) but the saturation and brightness is changed
    depending on the client is focused or not, using an HSV-to-RGB translation.

    However, experimentation shows that HSV isn't very good, as
    confirmed by
    http://www.poynton.com/notes/colour_and_gamma/ColorFAQ.html#RTFToC36

    Varying the brightness changes the perceived color, only just
    changing the saturation works reasonably well.  This might be a
    problem with the colorsys module, too.

    If anyone manages to understand it, maybe the CIE XYZ model should
    be tried instead.
    """

    class TitleUpdater:
        def __init__(self, manager, client):
            self.manager = manager
            self.client = client

        def __call__(self, event):
            if event.atom == Xatom.WM_NAME:
                self.manager.choose_color(self.client)

    def __init__(self, blurred_saturation = 0.3,
                 blurred_brightness = 0.7,
                 focused_saturation = 1.0,
                 focused_brightness = 0.7):

        """The saturation and brightness values should all be in the
        range [0.0, 1.0].

        As noted above, the two brightness values should typically be
        the same, otherwise the color will be perceived to change in
        hue when the window is focused.
        """

        self.blurred_saturation = blurred_saturation
        self.blurred_brightness = blurred_brightness
        self.focused_saturation = focused_saturation
        self.focused_brightness = focused_brightness

    def set_client_border_colors(self, client):
        # Add a dispatcher that updates the colors when the title changes
        client.dispatch.add_handler(X.PropertyNotify, self.TitleUpdater(self, client))

        # And set the initial colors
        self.choose_color(client)

    def choose_color(self, client):

        # FIXME: release old colors first to work well in PseudoColor
        # visuals.  Would require extensions to the color module,
        # though, reference counting and so on, and also an event
        # handler to free colors when the client is closed.

        hue = self.get_hue(client)

        blurred = self.get_color_hsv(client, hue,
                                     self.blurred_saturation,
                                     self.blurred_brightness)

        focused = self.get_color_hsv(client, hue,
                                     self.focused_saturation,
                                     self.focused_brightness)

        client.border_set_colors(blurred, focused)


    def get_hue(self, client):
        """Return the hue for this client, in the range [0.0, 1.0]"""

        # We can't really know the range of hash, but there's probably
        # at least 24 bits.  Xor them into eight bits and use that for hue

        th = hash(client.get_title())

        h = th & 0xff
        h ^= (th >> 8) & 0xff
        h ^= (th >> 16) & 0xff

        return float(h) / 0xff


    def get_color_hsv(self, client, hue, saturation, brightness):
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness)
        return client.screen.get_color((r * 65535, g * 65535, b * 65535))

