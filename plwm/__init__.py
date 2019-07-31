#
# __init__.py for package plwm
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

"""PLWM - The Pointless Window Manager

This module provides various window manager components, allowing you to build
your own window manager.
"""

__version_number__ = (2, 7)

__version_extra__ = 'rc1'

__version__ = '.'.join(map(str, __version_number__)) + __version_extra__

__all__ = [ 'border',
            'cfilter',
            'color',
            'composite',
            'cycle',
            'deltamove',
            'event',
            'filters',
            'focus',
            'font',
            'frame',
            'ido',
            'input',
            'inspect',
            'keys',
            'menu',
            'message',
            'misc',
            'modestatus',
            'modewindow',
            'moveresize',
            'mw_acpi',
            'mw_apm',
            'mw_biff',
            'mw_clock',
            'mw_load',
            'mw_watchfiles',
            'outline',
            'panes',
            'views',
            'wmanager',
            'wmevents',
            ]
