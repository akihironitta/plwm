#
# outline.py -- various client outline drawing functions
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


from Xlib import X
import wmanager

# Client mixin classes

class XorOutlineClient:

    """Create an outline by xoring the pixels on the screen.  This is
    the fastest method to create an outline, but if window content
    changes under the outline the outline cannot be hidden properly.

    Also, some combinations of depth, visuals and colormaps will not
    produce a visible outline for e.g. a black background.  Use the
    more expensive WindowOutlineClient in that case.
    """

    def __client_init__(self):
        self.outline_font = self.wm.get_font_res('.outline.font',
                                                 '.Outline.Font',
                                                 'fixed')

        self.outline_gc = self.screen.root.create_gc(
            function = X.GXxor,
            line_width = 0,
            foreground = (1 << self.screen.info.root_depth) - 1,
            subwindow_mode = X.IncludeInferiors,
            font = self.outline_font
            )

        self.outline_segments = None
        self.outline_name = None

    def outline_show(self, x = None, y = None, w = None, h = None, name = None):

        # Undraw a possible existing outline
        self.outline_hide()

        coords, self.outline_segments, namepos = \
                calculate_parts(self, x, y, w, h, name)

        self.screen.root.poly_segment(self.outline_gc, self.outline_segments)

        if name:
            self.outline_gc.set_clip_rectangles(0, 0, [coords], X.YXSorted)
            sx, sy, sw, sh, asc = namepos
            self.screen.root.draw_text(self.outline_gc, sx, sy, name)
            self.outline_name = (sx, sy, name)
        else:
            self.outline_name = None

    def outline_hide(self):
        if self.outline_segments:
            self.screen.root.poly_segment(self.outline_gc, self.outline_segments)
            self.outline_segments = None

        if self.outline_name:
            sx, sy, name = self.outline_name
            self.screen.root.draw_text(self.outline_gc, sx, sy, name)
            self.outline_gc.change(clip_mask = X.NONE)
            self.outline_name = None


class WindowOutlineClient:

    """Draw an outline by creating a grid of windows.  This avoids the
    messiness of windows changing their contents under an XorOutline,
    and it also works on all varieties of screen depth and color maps.

    The windows in the grid will simulate lines, by being one pixel
    wide and having a border width of one pixel.  The border is set to
    black and the window background is set to white, thus relying on
    the X server to clear the window area to create the line
    impression.

    The text, if any, is displayed in a separate window with black
    background and white foreground.  No tracking of Exposure is done,
    since the outline is always on top, at least when it is first shown.

    TODO: add X resources for the colours used by the outline.
    """

    def __client_init__(self):
        self.outline_font = self.wm.get_font_res('.outline.font',
                                                 '.Outline.Font',
                                                 'fixed')

        # Postpone allocattion of outline windows until
        # they are needed
        self.outline_windows = None
        self.outline_name_window = None
        self.outline_name_gc = None
        self.outline_mapped = 0

    def __client_del__(self):
        if self.outline_windows is None:
            return

        # Drop the resources held by the outline windows
        wmanager.debug('outline', 'freeing windows')
        for w in self.outline_windows:
            w.destroy()
        self.outline_name_gc.free()
        self.outline_name_window.destroy()

    def outline_show(self, x = None, y = None, w = None, h = None, name = None):
        coords, segments, namepos = \
                calculate_parts(self, x, y, w, h, name)

        if self.outline_windows is None:
            self.allocate_windows()

        for i in range(0, 8):
            w = self.outline_windows[i]
            s = segments[i]
            w.configure(x = s[0] - 1, y = s[1] - 1,
                        width = s[2] - s[0] + 1,
                        height = s[3] - s[1] + 1)

        if name:
            sx, sy, sw, sh, asc = namepos
            self.outline_name_window.configure(x = sx, y = sy - asc,
                                               width = sw, height = sh)

        if not self.outline_mapped:
            for w in self.outline_windows:
                w.configure(stack_mode = X.Above)
                w.map()
            if name:
                self.outline_name_window.configure(stack_mode = X.Above)
                self.outline_name_window.map()
            self.outline_mapped = 1

        # draw text first after having mapped the window, as it will
        # disappear otherwise...
        if name:
            self.outline_name_window.image_text(self.outline_name_gc,
                                                0, asc, name)

    def outline_hide(self):
        if self.outline_mapped:
            for w in self.outline_windows:
                w.unmap()
            self.outline_name_window.unmap()
            self.outline_mapped = 0

    def allocate_windows(self):
        self.outline_windows = []

        # Allocate horizontal and vertical bars
        for i in range(0, 8):
            w = self.screen.root.create_window(
                0, 0, 1, 1, 1, X.CopyFromParent,
                border_pixel = self.screen.info.black_pixel,
                background_pixel = self.screen.info.white_pixel,
                save_under = 1
                )
            self.outline_windows.append(w)

        # Allocate text window
        w = self.screen.root.create_window(
            0, 0, 1, 1, 1, X.CopyFromParent,
            border_pixel = self.screen.info.black_pixel,
            background_pixel = self.screen.info.black_pixel,
            save_under = 1
            )
        self.outline_name_window = w
        self.outline_name_gc = w.create_gc(
            foreground = self.screen.info.white_pixel,
            background = self.screen.info.black_pixel,
            font = self.outline_font
            )


def calculate_parts(client, x, y, w, h, name):
    """Calculates coordinates for drawing an outline.

    Returns three values: coords, segments, namepos

    coords is a four-tuple: (x, y, w, h), either the values
    supplied or taken from client if any values are None.

    segments is a list of four-tuples: (x1, y1, x2, y2), the
    coordinates to draw lines between.  Eight tuples are returned:
    first the four horizontal lines in order from top to bottom,
    then the four vertical lines, from left to right.

    namepos is a four-tuple: (x, y, w, h), the coordinates to draw the
    name at (if supplied), and its width and height.
    """

    if x is None:
        x = client.x
    if y is None:
        y = client.y
    if w is None:
        w = client.width + 2 * client.border_width
    if h is None:
        h = client.height + 2 * client.border_width

    s = []
    w3 = w / 3
    h3 = h / 3
    xr = x + w - 1
    yt = y + 1
    yb = y + h - 2

    # Horizontal lines
    s.append((x, y, xr, y))
    s.append((x + 1, y + h3, xr - 1, y + h3))
    s.append((x + 1, y + h3 + h3, xr - 1, y + h3 + h3))
    s.append((x, y + h - 1, xr, y + h - 1))

    # Vertical lines
    s.append((x, yt, x, yb))
    s.append((x + w3, yt, x + w3, yb))
    s.append((x + w3 + w3, yt, x + w3 + w3, yb))
    s.append((xr, yt, xr, yb))

    if name:
        # Center string
        r = client.outline_font.query_text_extents(name)

        sx = max(x + (w - r.overall_width) / 2, x)
        sy = y + h / 2 + (r.overall_ascent + r.overall_descent) / 2 - r.overall_descent

        sw = min(r.overall_width, w)
        sh = min(r.overall_ascent + r.overall_descent, h)
        asc = r.overall_ascent
    else:
        sx = sy = sw = sh = asc = 0

    return (x, y, w, h), s, (sx, sy, sw, sh, asc)
