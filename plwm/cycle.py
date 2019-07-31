#
# cycle.py -- Cycle among clients to select one to activate
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
import keys
import cfilter
import wmanager

class NoClientsError(Exception): pass

class Cycle:
    def __init__(self, screen, client_filter):
        self.clients = screen.query_clients(client_filter, stackorder = 1)
        if not self.clients:
            raise NoClientsError('No clients matching filter')
        self.clients.reverse()

        self.ix = 0
        self.mark()

    def next(self):
        self.unmark()
        self.ix = (self.ix + 1) % len(self.clients)
        self.mark()

    def previous(self):
        self.unmark()
        self.ix = (self.ix - 1) % len(self.clients)
        self.mark()

    def end(self):
        self.unmark()

    def abort(self):
        self.unmark()

    def mark(self):
        pass

    def unmark(self):
        pass


class CycleActivate(Cycle):
    """Cycle among clients by activating each window in turn.

    Iconified windows will go back to being iconified when we step to
    the next window.
    """

    def mark(self):
        self.last_mapped = self.clients[self.ix].is_mapped()
        self.clients[self.ix].activate()

    def unmark(self):
        if not self.last_mapped:
            self.clients[self.ix].iconify()

    def end(self):
        pass


class CycleOutline(Cycle):
    """Cycle among clients by drawing an outline for each one.
    """

    def mark(self):
        self.clients[self.ix].outline_show(name = self.clients[self.ix].get_title())

    def unmark(self):
        self.clients[self.ix].outline_hide()

    def end(self):
        Cycle.end(self)
        self.clients[self.ix].activate()


#
# KeyHandler template for cycling
#

class CycleKeys(keys.KeyGrabKeyboard):

    """CycleKeys is a template keyhandler for cycling clients.
    You should subclass it to define your own keybindings and setting
    the approriate client filter.

    The filter for the cycle is specified by the attribute _cycle_filter.
    This can be set to any client filter, by default `true' is used.

    CycleKeys defines a number of event handler methods:

      _cycle_next      Cycle to the next client
      _cycle_previous  Cycle to the previous client
      _cycle_end       Finish, selecting the current client
      _cycle_abort     Abort, reverting to the previous state (if possible)

    By default outline cycling is used with the CycleOutline class.
    This can be changed by redefining the attribute _cycle_class to
    any subclass of Cycle.

    A small CycleKeys subclass example:

      class MyCycleKeys(CycleKeys):
         _cycle_class = CycleActivate
         _cycle_filter = cfilter.Not(cfilter.iconified)

         Tab = CycleKeys._cycle_next
         C_Tab = CycleKeys._cycle_next
         S_Tab = CycleKeys._cycle_previous
         S_C_Tab = CycleKeys._cycle_previous

         Return = CycleKeys._cycle_end
         Escape = CycleKeys._cycle_abort


    To activate your cycle keys, write a keyhandler event method like
    this in your basic keyhandler:

      def C_Tab(self, evt):
         MyCycleKeys(self, evt)

    """

    propagate_keys = 0
    timeout = 10

    _cycle_class = CycleOutline
    _cycle_filter = cfilter.true

    def __init__(self, keyhandler, event):
        # Always initialize the keyhandler, otherwise
        # we'll get problems in the __del__ method.

        try:
            keys.KeyGrabKeyboard.__init__(self, keyhandler.wm, event.time)
        except keys.error, status:
            wmanager.debug('keys', 'Grabbing keyboard failed: %d', status)

        # Create the cycle object, but clean up and return immediately
        # if no clients match the filter
        try:
            wmanager.debug('keys', 'Entering cycle mode')
            self.cycle = self._cycle_class(keyhandler.wm.current_screen,
                                           self._cycle_filter)
        except NoClientsError:
            wmanager.debug('keys',
                           'No clients matching cycle filter, leaving cycle mode')
            self._cleanup()

    def _cycle_next(self, evt):
        self.cycle.next()

    def _cycle_previous(self, evt):
        self.cycle.previous()

    def _cycle_end(self, evt):
        wmanager.debug('keys', 'Leaving cycle mode')
        self.cycle.end()
        self._cleanup()


    def _cycle_abort(self, evt):
        wmanager.debug('keys', 'Aborting cycle mode')
        self.cycle.abort()
        self._cleanup()

    _timeout = _cycle_abort

