#
# cfilter.py -- Client filter functions
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

"""plwm.filter contains various classes and functions which can be
used to create client filters.  These client filters can be used in
various places, e.g. for selecting whether a client window should have
a frame, which clients to cycle among for selection, etc.

A filter is called with one argument, a client object.  The return
value is true or false, depending on how the filter evaluated for the
client.

Simple filter functions:

  true, all     always true
  false, none   always false
  is_client     true if the object is a wmanager.Client instance

  iconified     true if the client is iconified
  mapped        true if the client is mapped

Functions matching the client resource name (i.e. res_name or res_class):

  name(string)     true if the name exactly matches string
  re_name(regexp)  true if the name matches the regexp string
  glob_name(glob)  true if the name matches the glob string

Functions matching the client title:

  title(string)     true if the title exactly matches string
  re_title(regexp)  true if the title matches the regexp string
  glob_title(glob)  true if the title matches the glob string

Compound filters:

  And(filter, filter...)  true if all the filters are true
  Or(filter, filter...)   true if any of the filters are true
  Not(filter)             true if the filter is false

"""

import re
import fnmatch

import wmanager
import filters

# For backward compitability
from filters import true, all, false, none, And, Or, Not


class _IsClient(filters.Filter):
    NAME = 'is_client'

    def __call__(self, c):
        return isinstance(c, wmanager.Client)

is_client = _IsClient()


class _Iconified(filters.Filter):
    NAME = 'iconified'
    def __call__(self, c):
        return not c.is_mapped()

iconified = _Iconified()


class _Mapped(filters.Filter):
    NAME = 'mapped'
    def __call__(self, c):
        return c.is_mapped()

mapped = _Mapped()


class _NameBase(filters.Filter):
    def __init__(self, pattern):
        super(_NameBase, self).__init__()
        self.pattern = pattern

    def check(self, str):
        if str is None:
            return self.pattern is None
        else:
            return self.check_pattern(str)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self.pattern))


class _StringName(_NameBase):
    def check_pattern(self, str):
        return self.pattern == str

class _ReName(_NameBase):
    def __init__(self, pattern):
        super(_ReName, self).__init__(re.compile(pattern))

    def check_pattern(self, str):
        return self.pattern.search(str) is not None

class _GlobName(_NameBase):
    def check_pattern(self, str):
        return fnmatch.fnmatchcase(str, self.pattern)

class _Title:
    def __call__(self, c):
        return self.check(c.get_title())

class _Resource:
    def __call__(self, c):
        return self.check(c.res_name) or self.check(c.res_class)

class name(_StringName, _Resource): pass
class re_name(_ReName, _Resource): pass
class glob_name(_GlobName, _Resource): pass

class title(_StringName, _Title): pass
class re_title(_ReName, _Title): pass
class glob_title(_GlobName, _Title): pass
