# -*- coding: iso-8859-1 -*-
#
# mw_acpi.py -- display ACPI AC/battery status in a modewindow
#
#    Copyright (C) 2004  Peter Liljenberg <petli@ctrl-c.liu.se>
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

from plwm import modewindow, event, wmanager
import sys
import os
import time
import re
import socket

TimerEventType = event.new_event_type()
ACPIEventType = event.new_event_type()



# ACPI interface:

#  probe: check if interface is present

#  get_event_socket: return an event socket, if any

#  handle_event_socket: process data read from event socket, return
#  pair with new status: (status, numbeeps), or None if no change.

#  poll: check all data, return pair (status, numbeeps) or None as above

class BadInfo(Exception): pass


class LinuxProcACPI:
    acpid_socket = '/var/run/acpid.socket'

    event_re = re.compile(r'^(\S+) (\S+) ')

    class AcAdapter:
        EVENT = 'ac_adapter'
        PROC_DIR = '/proc/acpi/ac_adapter'

        STATE = 'state'
        ONLINE = 'on-line'

        def __init__(self, id, path):
            self.id = id
            self.path = path
            self.messsage = ''

            self.state = None

            self.update()

        def update(self):
            state = linux_proc_read_state(self.path)

            if self.state != state[self.STATE]:
                self.state = state[self.STATE]
                if self.state == self.ONLINE:
                    self.message = 'AC'
                else:
                    self.message = ''

                return 1
            else:
                return 0


    class Battery:
        EVENT = 'battery'
        PROC_DIR = '/proc/acpi/battery'

        PRESENT = 'present'
        MAX = 'design capacity'
        STATE = 'charging state'
        RATE = 'present rate'
        REMAIN = 'remaining capacity'

        mW_re = re.compile(r'^(\d+) m[AW]$')
        mWh_re = re.compile(r'^(\d+) m[AW]h$')

        def __init__(self, id, path):
            self.id = id
            self.path = path
            self.messsage = ''

            self.state = None
            self.rate = None
            self.remain = None

            info = linux_proc_read_info(self.path)

            try:
                # Fetch all values from state
                if info[self.PRESENT] != 'yes':
                    raise BadInfo('battery %s not present (value: %s)' % (self.id, info[self.PRESENT]))

                m = self.mWh_re.match(info[self.MAX])
                if m is None:
                    raise BadInfo('expected mWh value: %s' % info[self.MAX])

                self.max = int(m.group(1))
                self.update()

            except KeyError, e:
                raise BadInfo('battery %s missing required info: %s' % (self.id, e))


        def update(self):
            state = linux_proc_read_state(self.path)

            new_state = state[self.STATE]
            new_rate = state[self.RATE]
            new_remain = state[self.REMAIN]

            # Check values
            if new_state not in ('charged', 'unknown', 'discharging', 'charging'):
                raise BadInfo('unknown charging state: %s' % new_state)

            if new_rate != 'unknown':
                m = self.mW_re.match(new_rate)
                if m is None:
                    raise BadInfo('expected mW value: %s' % new_rate)
                new_rate = int(m.group(1))
            else:
                new_rate = None

            m = self.mWh_re.match(new_remain)
            if m is None:
                raise BadInfo('expected mWh value: %s' % new_remain)
            new_remain = int(m.group(1))

            updated = (new_state != self.state
                       or new_rate != self.rate
                       or new_remain != self.remain)

            if updated:
                self.state = new_state
                self.rate = new_rate
                self.remain = new_remain

                # Calculate percentage and remaning time
                self.percent = int(100.0 * self.remain / self.max)

                remaining = 0

                if self.rate is not None:
                    if self.state == 'charging':
                        remaining = self.max - self.remain
                    elif self.state == 'discharging':
                        remaining = self.remain

                if remaining > 0:
                    self.seconds_left = (3600 * remaining) / self.rate
                    secstr = ' (%d:%02d:%02d)' % (self.seconds_left / 3600,
                                                  (self.seconds_left / 60) % 60,
                                                  self.seconds_left % 60)
                else:
                    self.seconds_left = None
                    secstr = ''

                if self.state == 'discharging':
                    self.message = '%d%%%s' % (self.percent, secstr)
                elif self.state == 'charging':
                    self.message = 'charging %d%%%s' % (self.percent, secstr)
                else:
                    self.message = ''

            return updated


    class Processor:
        EVENT = 'processor'
        PROC_DIR = '/proc/acpi/processor'

        PERFORMANCE_MANAGEMENT = 'performance management'
        THROTTLING_CONTROL = 'throttling control'

        ACTIVE_STATE = 'active state'

        FREQ_RE = re.compile(r'^(\d+) MHz')
        PERCENT_RE = re.compile(r'^(\d+)%')

        def __init__(self, id, path):
            self.id = id
            self.path = path
            self.performance_file = os.path.join(path, 'performance')
            self.throttling_file = os.path.join(path, 'throttling')

            self.messsage = ''

            info = linux_proc_read_info(path)
            self.has_performance = info.get(self.PERFORMANCE_MANAGEMENT) == 'yes'
            self.has_throttling = info.get(self.THROTTLING_CONTROL) == 'yes'

            if not self.has_performance and not self.has_throttling:
                raise BadInfo('neither performance nor throttling control, nothing to display')

            self.performance_state = None
            self.performance_freq = None

            self.throttling_state = None
            self.throttling_percent = None

            self.update()

        def update(self):
            change = 0

            if self.has_performance:
                perf = linux_proc_read_values(self.performance_file)

                if self.performance_state != perf[self.ACTIVE_STATE]:
                    self.performance_state = perf[self.ACTIVE_STATE]

                    try:
                        freq = perf['*%s' % self.performance_state]
                    except KeyError:
                        raise BadInfo('unknown performance state: %s' % self.performance_state)

                    m = self.FREQ_RE.match(freq)
                    if not m:
                        raise BadInfo('unknown performance info: %s' % freq)

                    self.performance_freq = int(m.group(1))
                    change = 1


            if self.has_throttling:
                thr = linux_proc_read_values(self.throttling_file)

                if self.throttling_state != thr[self.ACTIVE_STATE]:
                    self.throttling_state = thr[self.ACTIVE_STATE]

                    try:
                        percent = thr['*%s' % self.throttling_state]
                    except KeyError:
                        print thr
                        raise BadInfo('unknown throttling state: %s' % self.throttling_state)

                    m = self.PERCENT_RE.match(percent)
                    if not m:
                        raise BadInfo('unknown throttling info: %s' % percent)

                    self.throttling_percent = int(m.group(1))
                    change = 1

            if change:
                msg = []
                if self.has_performance:
                    msg.append('%dMHz' % self.performance_freq)

                if (self.has_throttling
                    and self.throttling_percent > 0
                    and self.throttling_percent < 100):
                    msg.append('T%d%%' % self.throttling_percent)

                self.message = ' '.join(msg)
                return 1
            else:
                return 0


    class ThermalZone:
        EVENT = None
        PROC_DIR = '/proc/acpi/thermal_zone'

        STATE = 'state'
        TEMPERATURE = 'temperature'

        DEGREE_RE = re.compile(r'^(\d+) C$')

        def __init__(self, id, path):
            self.id = id
            self.path = path
            self.temperature_file = os.path.join(path, 'temperature')

            self.messsage = ''

            self.degrees = None

            self.update()

        def update(self):
            temps = linux_proc_read_values(self.temperature_file)

            m = self.DEGREE_RE.match(temps[self.TEMPERATURE])
            if not m:
                raise BadInfo('bad temperature: %s' % temps[self.TEMPERATURE])

            new_degrees = int(m.group(1))

            if self.degrees != new_degrees:
                self.degrees = new_degrees
                self.message = '%d°C' % self.degrees
                return 1
            else:
                return 0


    # Not really ACPI, this one.  But on Linux 2.6 kernels, the CPU frequency isn't
    # displayed in the ACPI interface, but from the cpu-freq module.

    class CpuFreqScaling:
        EVENT = None
        PROC_DIR = '/sys/devices/system/cpu'

        SCALING_CPU_FREQ = '%s/cpufreq/scaling_cur_freq'

        def __init__(self, id, path):
            self.id = id
            self.path = path

            self.scaling_cpu_freq = self.SCALING_CPU_FREQ % (path, )

            self.messsage = ''

            # frequency in kHz
            self.freq = None

            self.update()

        def update(self):
            try:
                new_freq = int(open(self.scaling_cpu_freq).read(50))
            except (IOError, ValueError), e:
                raise BadInfo('bad cpufreq: %s: %s' % (self.scaling_cpu_freq, e))

            if self.freq != new_freq:
                self.freq = new_freq
                self.message = '%d MHz' % (self.freq / 1000)
                return 1
            else:
                return 0


    def __init__(self):
        self.socket = None
        self.event_data = ''

        self.status_changed = 0

        self.infos = []

        # Map of (class, unit) -> object
        self.units = {}


    def add_units(self, cls):
        for unit, path in self.find_units(cls.PROC_DIR):
            try:
                b = cls(unit, path)
                self.infos.append(b)
                self.units[(cls.EVENT, unit)] = b
            except (IOError, BadInfo), e:
                wmanager.debug('acpi', 'could not add %s %s: %s', cls.__name__, unit, e)


    def find_units(self, path):
        try:
            subdirs = os.listdir(path)
        except OSError, e:
            wmanager.debug('acpi', 'no such dir: %s', path)
            return ()

        subdirs.sort()

        return [ (d, os.path.join(path, d))
                 for d in subdirs
                 if os.path.isdir(os.path.join(path, d)) ]


    def handle_event(self, eventstr):
        m = self.event_re.match(eventstr)
        if not m:
            wmanager.debug('acpi', 'could parse event, closing socket:', eventstr)
            self.socket.close()
            return

        event = m.group(1).replace('/', '_')
        arg = m.group(2)

        try:
            unit = self.units[(event, arg)]
        except KeyError:
            wmanager.debug('acpi', 'unknown event: %s', eventstr)
            return

        if unit.update():
            self.status_changed = 1


    # Interface functions below
    def probe(self):
        if os.path.isdir('/proc/acpi'):
            wmanager.debug('acpi', 'using Linux proc interface')

            # See if there's also an acpid demon
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.connect(self.acpid_socket)
            except socket.error:
                wmanager.debug('acpi', 'could not open %s, relying solely on polling', self.acpid_socket)
                self.socket = None


            self.add_units(self.AcAdapter)
            self.add_units(self.Battery)
            self.add_units(self.Processor)
            self.add_units(self.CpuFreqScaling)
            self.add_units(self.ThermalZone)

            return 1
        else:
            return 0

    def get_event_socket(self):
        return self.socket

    def handle_event_socket(self, data):
        self.event_data += data

        self.status_changed = 0

        while 1:
            lines = self.event_data.split('\n', 1)

            # Not a complete line, stop
            if len(lines) == 1:
                break

            event = lines[0]
            self.event_data = lines[1]

            wmanager.debug('acpi', 'got event: %s', event)
            self.handle_event(event)

        if self.status_changed:
            return ('  '.join([i.message for i in self.infos if i.message]), 0)
        else:
            return None


    def poll(self, force):
        self.status_changed = 0

        for i in self.infos:
            if i.update():
                self.status_changed = 1

        if self.status_changed or force:
            return ('  '.join([i.message for i in self.infos if i.message]), 0)
        else:
            return None


LINUX_PROC_VALUE_RE = re.compile(r'^\s*([^:]+):' '[ \t]' r'*(.*\S)\s*$', re.MULTILINE)

def linux_proc_read_values(file):
    """Read a key: value file, returning a map of strings"""
    data = open(file).read()
    values = LINUX_PROC_VALUE_RE.findall(data)
    return dict(values)

def linux_proc_read_state(dir):
    return linux_proc_read_values(os.path.join(dir, 'state'))

def linux_proc_read_info(dir):
    return linux_proc_read_values(os.path.join(dir, 'info'))




acpi_interfaces = [ LinuxProcACPI(), ]


# wm mixin
class ModeWindowACPI:
    mw_acpi_position = 0.2
    mw_acpi_justification = modewindow.RIGHT
    mw_acpi_degree_symbol = "°"

    def __wm_init__(self):
        # Figure out which ACPI interface to use
        for ai in acpi_interfaces:
            if ai.probe():
                self.mw_acpi_interface = ai
                break
        else:
            # No matching ACPI interface, skip rest of our installation
            sys.stderr.write('%s: failed to find a parsable ACPI interface, disabling mw_acpi' % sys.argv[0])
            return

        self.mw_acpi_message = modewindow.Message(self.mw_acpi_position,
                                                   self.mw_acpi_justification)
        for s in self.screens:
            s.modewindow_add_message(self.mw_acpi_message)

        self.dispatch.add_handler(TimerEventType, self.mw_acpi_tick)

        self.mw_acpi_socket = ai.get_event_socket()
        if self.mw_acpi_socket:
            self.dispatch.add_handler(ACPIEventType, self.mw_acpi_handle_socket_event)
            self.mw_acpi_socket_event = event.FileEvent(ACPIEventType,
                                                        self.mw_acpi_socket,
                                                        event.FileEvent.READ)
            self.events.add_file(self.mw_acpi_socket_event)

        self.mw_acpi_poll(1)

    def mw_acpi_update(self, newstatus):
        if newstatus is not None:
            msg, beeps = newstatus

            self.mw_acpi_message.set_text(msg.replace("°", self.mw_acpi_degree_symbol))

            # Beep if status have changed
            if beeps:
                for i in range(beeps):
                    self.display.bell(100)


    def mw_acpi_tick(self, evt):
        self.mw_acpi_poll()

    def mw_acpi_poll(self, force = 0):
        # Recheck in 30 seconds: schedule this before polling, if that
        # produces an exception in parsing the ACPI info
        self.events.add_timer(event.TimerEvent(TimerEventType, after = 30))

        newstatus = self.mw_acpi_interface.poll(force)
        self.mw_acpi_update(newstatus)



    def mw_acpi_handle_socket_event(self, evt):
        if evt.state & event.FileEvent.READ:
            try:
                data = self.mw_acpi_socket.recv(200)
            except socket.error, e:
                wmanager.debug('acpi', 'failed to receive from event socket: %s', e)
                data = ''

            if data:
                newstatus = self.mw_acpi_interface.handle_event_socket(data)
                self.mw_acpi_update(newstatus)
            else:
                wmanager.debug('acpi', 'event socket closed')
                self.mw_acpi_socket.close()
                self.mw_acpi_socket = None
                self.mw_acpi_socket_event.cancel()
