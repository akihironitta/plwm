#
# color.py -- Handle colors in a more symbolic way
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


import types

class ColorError(Exception): pass


# Screen mixin class
class Color:
    def __screen_client_init__(self):
        self.color_map = self.info.default_colormap
        self.color_alloced = {}

    def get_color(self, color, default = None):
        """Return the pixel value corresponding to COLOR.
        COLOR can be a string or tuple of (R, G, B).

        If the color can't be found and DEFAULT is provided, try to
        return that color instead.
        """

        try:
            return self.color_alloced[color]
        except KeyError:
            pass

        if type(color) is types.StringType:
            col = self.color_map.alloc_named_color(color)
        elif type(color) is types.TupleType and len(color) == 3:
            col = self.color_map.alloc_color(color[0], color[1], color[2])
        else:
            raise TypeError("string or 3-tuple expected")

        # If color allocation fails and there is a default color, simply
        # recurse to try to allocate it
        if col is None:
            if default:
                return self.get_color(default)
            else:
                raise ColorError(color)
        else:
            self.color_alloced[color] = col.pixel

        return self.color_alloced[color]

    def get_color_res(self, res_name, res_class, default = None):
        """Return the pixel value for the color defined in
        the X resource RES_NAME/RES_CLASS.

        If DEFAULT is provided, that name will be used if no matching
        X resource is found.  If omitted, ColorError will be raised.
        """
        col = self.wm.rdb_get(res_name, res_class, default)
        if col is None:
            raise ColorError('No color resource defined for %s/%s' % (res_name, res_class))

        return self.get_color(col, default)

