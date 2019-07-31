#
# mw_clock.py -- display the time in a ModeWindow
#
#    Copyright (C) 2001  Peter Liljenberg <petli@ctrl-c.liu.se>
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


from plwm import modewindow, event, wmanager
import time

ClockEventType = event.new_event_type()

# wm mixin
class ModeWindowClock:
    mw_clock_position = 1.0
    mw_clock_justification = modewindow.RIGHT

    def __wm_init__(self):
        self.mw_clock_format = self.rdb_get('.modewindow.clock.format',
                                            '.ModeWindow.Clock.Format',
                                            '%H:%M')

        self.mw_clock_message = modewindow.Message(self.mw_clock_position,
                                                   self.mw_clock_justification)
        for s in self.screens:
            s.modewindow_add_message(self.mw_clock_message)

        self.dispatch.add_handler(ClockEventType, self.mw_clock_tick)

        self.mw_clock_update()

    def mw_clock_update(self):
        t = time.localtime(time.time())
        s = time.strftime(self.mw_clock_format, t)
        self.mw_clock_message.set_text(s)

        wmanager.debug('clock', 'updated to "%s", rescheduling in %d seconds',
                       s, 61 - t[5])

        # Trig a timer when minute change
        self.events.add_timer(event.TimerEvent(ClockEventType, after = 61 - t[5]))

    def mw_clock_tick(self, evt):
        self.mw_clock_update()
