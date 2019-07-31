#
# filters.py -- Core filter functionality
#
#    Copyright (C) 2009  Peter Liljenberg <peter.liljenberg@gmail.com>
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

This module contains filter functionality that is common to both
client and event filters.

It contains the following general filters:

  true, all      always true
  false, none    always false

  And(filter, filter...)  true if all the filters are true
  Or(filter, filter...)   true if any of the filters are true
  Not(filter)             true if the filter is false
"""


# We must use class objects everywhere.  This is caused by the method
# semantics used in slightly older Python versions: anytime we get the
# value of an attribute in a class, and that value is a function, it
# is converted into a method object.  Since it is likely that filters
# will be assigned to class attributes, e.g. Client.start_iconified,
# we can't allow any filter to be ordinary functions.  So instead we
# use Python objects with a __call__ method to circumvent this
# problem.

# Starting with Python 2.5 (2.4?) the semantics changed and we could
# probably use normal functions instead.  However, using objects
# allows a better str() implementation and opens up the possibility to
# do smart things to improve event filter processing.

# To limit the performance penalty we sets self.__call__ to
# self.__call__.  This subtle little assignment will fetch the unbound
# __call__ method from the class dict, bind it to the instance and
# assign it to the instance dict.  This reduces each filter invokation
# to a normal function call.  Additionally, this avoids having to
# traverse the class tree to find the method.

class Filter(object):
    name = None

    def __init__(self):
        if self.name is None:
            self.name = self.__class__.__name__
            
        self.__call__ = self.__call__

    def __str__(self):
        return self.name


class _True(Filter):
    name = 'true'
    def __call__(self, obj):
        return True

true = _True()
all = true

class _False(Filter):
    name = 'false'
    def __call__(self, obj):
        return False

false = _False()
none = false

class And(Filter):
    """
    True if all filters are true.  Evaluation is short-circuited and
    will return as soon as one filter is false.
    """

    def __init__(self, *args):
        super(And, self).__init__()
        self.filters = args

    def __call__(self, obj):
        for f in self.filters:
            if not f(obj):
                return False
        return True

    def __str__(self):
        return 'And(%s)' % ', '.join([str(f) for f in self.filters])


class Or(Filter):
    """
    True if all filters are true.  Evaluation is short-circuited and
    will return as soon as one filter returns true.
    """

    def __init__(self, *args):
        super(Or, self).__init__()
        self.filters = args

    def __call__(self, obj):
        for f in self.filters:
            if f(obj):
                return True
        return False

    def __str__(self):
        return 'Or(%s)' % ', '.join([str(f) for f in self.filters])


class Not(Filter):
    def __init__(self, filter):
        super(Not, self).__init__()
        self.filter = filter

    def __call__(self, obj):
        return not self.filter(obj)

    def __str__(self):
        return 'Not(%s)' % str(self.filter)

