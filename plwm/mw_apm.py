#
# mw_apm.py -- display APM status in a modewindow
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
#
# NetBSDIoctlAPM interface contributed by Henrik Rindlöw.

from plwm import modewindow, event, wmanager
import sys
import time
import re
import fcntl
import struct

TimerEventType = event.new_event_type()

class LinuxProcAPM:
    apm_file = '/proc/apm'
    apm_re = re.compile(r'^1\.\d+ (?P<bios_version>\d+\.\d+) '
                        r'0x(?P<bios_flags>[0-9a-f]+) 0x(?P<ac_line>[0-9a-f]+) '
                        r'0x(?P<battery_status>[0-9a-f]+) '
                        r'0x(?P<battery_flag>[0-9a-f]+) '
                        r'(?P<charge_percentage>-?\d+)% '
                        r'(?P<charge_time>-?\d+) (?P<time_units>\S*)')

    battery_status_codes = {
        '00': ('High', 0),
        '01': ('Low', 1),
        '02': ('Critical', 2),
        '03': ('Charging', 0),
        '04': ('Missing', 0),
        }

    def __init__(self):
        self.old_status = None

    def get_match(self):
        try:
            f = open(self.apm_file, 'r')
        except IOError:
            return None

        line = f.read(100)
        return self.apm_re.match(line)

    # Interface functions below
    def probe(self):
        return (self.get_match() is not None)

    def get(self):
        m = self.get_match()
        if m is None:
            return None, None

        msg = ''

        if m.group('ac_line') == '01':
            msg = msg + 'AC '

        raw_status = m.group('battery_status')
        status, beeps = self.battery_status_codes.get(raw_status,
                                                      ('Unknown', 0))
        msg = msg + status

        perc = int(m.group('charge_percentage'))
        if perc >= 0 and perc <= 100:
            msg = msg + ': %d%%' % perc

        ctime = int(m.group('charge_time'))
        if ctime >= 0:
            msg = msg + ' %d %s' % (ctime, m.group('time_units'))

        # Cancel out beeps if status hasn't changed
        if self.old_status == raw_status or self.old_status is None:
            beeps = 0
        self.old_status = raw_status

        return msg, beeps


class NetBSDIoctlAPM:
    apm_dev = '/dev/apm'
    api = struct.pack('4B7I', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    APM_IOC_GETPOWER = 0x40004103 | (len(api) << 16)
    battery_status_codes = {
        0: ('High', 0),
        1: ('Low', 1),
        2: ('Critical', 2),
        3: ('Charging', 0),
        4: ('Missing', 0),
        }

    def __init__(self):
        self.old_status = None

    def do_ioctl(self):
        try:
            apm = open(self.apm_dev)
            return fcntl.ioctl(apm.fileno(), self.APM_IOC_GETPOWER, self.api)
        except IOError:
            return None

    # Interface functions below
    def probe(self):
        return (self.do_ioctl() is not None)

    def get(self):
        api = self.do_ioctl()
        if api is None:
            return None, None

        (battery_state,
         ac_state,
         battery_life,
         spare1,
         minutes_left,
         spare2,
         spare3,
         spare4,
         spare5,
         spare6,
         spare7) = struct.unpack('4B7I', api)

        msg = ''


        if ac_state == 1:
            msg = msg + 'AC '

        status, beeps = self.battery_status_codes.get(battery_state,
                                                      ('Unknown', 0))
        msg = msg + status

        if battery_life >= 0 and battery_life <= 100:
            msg = msg + ': %d%%' % battery_life

        if minutes_left > 0:
            msg = msg + ' %d minutes' % minutes_left

        # Cancel out beeps if status hasn't changed
        if self.old_status == battery_state or self.old_status is None:
            beeps = 0
        self.old_status = battery_state

        return msg, beeps

apm_interfaces = [ LinuxProcAPM(), NetBSDIoctlAPM() ]



# wm mixin
class ModeWindowAPM:
    mw_apm_position = 0.2
    mw_apm_justification = modewindow.RIGHT

    def __wm_init__(self):
        # Figure out which APM interface to use
        for ai in apm_interfaces:
            if ai.probe():
                self.mw_apm_interface = ai
                break
        else:
            # No matching APM interface, skip rest of our installation
            sys.stderr.write('%s: failed to find a parsable APM interface, disabling mw_apm' % sys.argv[0])
            return

        self.mw_apm_message = modewindow.Message(self.mw_apm_position,
                                                   self.mw_apm_justification)
        for s in self.screens:
            s.modewindow_add_message(self.mw_apm_message)

        self.dispatch.add_handler(TimerEventType, self.mw_apm_tick)

        self.mw_apm_update()

    def mw_apm_update(self):
        msg, beeps = self.mw_apm_interface.get()

        self.mw_apm_message.set_text(msg)

        # Beep if status have changed
        if beeps:
            for i in range(beeps):
                self.display.bell(100)

        # Recheck in 30 seconds
        self.events.add_timer(event.TimerEvent(TimerEventType, after = 30))

    def mw_apm_tick(self, evt):
        self.mw_apm_update()
