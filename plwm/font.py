#
# font.py -- handle fonts in a more symbolic way
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

class FontError(Exception): pass

# WindowManager mixin class
class Font:
    def get_font(self, fontname, default = None):
        """Return the font object corresponding to FONTNAME.

        If FONTNAME doesn't match any font, attemt to return
        the font named DEFAULT instead, if DEFAULT is provided.

        If no font can be found, FontError is raised
        """

        font = self.display.open_font(fontname)

        if font is None:
            if default is None:
                raise FontError("can't open font %s" % fontname)

            font = self.display.open_font(default)
            if font is None:
                raise FontError("can't open font %s" % fontname)

        return font

    def get_font_res(self, res_name, res_class, default = None):
        """Return the font object corresponding to the X
        resource RES_NAME, RES_CLASS.

        If this resource isn't found or doesn't match any font, attemt
        to return the font named DEFAULT instead, if DEFAULT is
        provided.

        If no font can be found, FontError is raised
        """

        fontname = self.rdb_get(res_name, res_class, default)
        if fontname is None:
            raise FontError('No font resource defined for %s/%s'
                            % (res_name, res_class))

        return self.get_font(fontname)

