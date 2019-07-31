# mw_load.py -- display load averages in a modewindow
#
#    Copyright (C) 2001  Meik Hellmund <hellmund@itp.uni-leipzig.de>
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
#  contributed by Meik Hellmund <hellmund@itp.uni-leipzig,de>, heavily reusing
#  other plwm code
#
# Two methods are tried to get the load averages:
# LinuxLoad - read from a file (/proc/loadavg)
# UnixLoad  - read output from a command (/usr/bin/uptime)
# In both cases, the output  is split on whitespaces and, depending on the
# displaylist variable, some elements of this list are shown.
#
#
# configuration variables:
#   mw_load_position,  mw_load_justification: describe the position in
#                                            the modeline, as usual
#   mw_load.LinuxLoad.loadfile: name of file to read
#   mw_load.LinuxLoad.displaylist: list of entries to be displayed
#                0,1,2 : 1,5,15-min load average
#                    4 : no. of running processes and total number of processes
#   mw_load.UnixLoad.loadcmd: command which prints load averages
#   mw_load.UnixLoad.displaylist: list of entries to be displayed
#       (for my uptime command, numbers 9,10 and 11 are the load averages)




from plwm import modewindow, event, wmanager
import os.path
import string
import sys
import re
import errno

LoadTimerEvent = event.new_event_type()

class LinuxLoad:
    loadfile = "/proc/loadsavg"
    displaylist = [0,1,2,3]

    def probe(self):
        return os.path.isfile(self.loadfile)

    def get(self, wm):
        f=open(self.loadfile,'r')
        l=string.split(f.readline())
        f.close()
        str=""
        for x in self.displaylist:
            str = str + l[x] + " "
        return string.strip(str)

class UnixLoad:
    loadcmd = "/usr/bin/uptime"
    load_re = re.compile(r'(\d+.\d\d)[, ]+(\d+.\d\d)[, ]+(\d+.\d\d)')

    def probe(self):
        return os.path.isfile(self.loadcmd)

    def get(self, wm):
        pipes = wm.system(self.loadcmd, redirect = 1)
        out = pipes[1]

        try:
            s = out.readline()
        except IOError, err:
            if err.errno == errno.EINTR:
                s = out.readline()
        out.close()

        wmanager.debug('mw_load', 'output: %s', s)

        m = self.load_re.search(s)
        if m:
            return string.join(m.groups(), ' ')
        else:
            return ''

load_interfaces = [ LinuxLoad(),
                    UnixLoad() ]

class ModeWindowLoad:
    mw_load_position = 0.05
    mw_load_justification = modewindow.LEFT


    def __wm_init__(self):
        for i in load_interfaces:
            if i.probe():
                self.mw_load_interface = i
                break
        else:
            sys.stderr.write('%s: failed to find a load interface, disabling mw_load\n' % sys.argv[0])
            return

        self.mw_load_message = modewindow.Message(self.mw_load_position,
                                                   self.mw_load_justification)
        for s in self.screens:
            s.modewindow_add_message(self.mw_load_message)

        self.dispatch.add_handler(LoadTimerEvent, self.mw_load_tick)
        self.mw_load_update()


    def mw_load_update(self):
        msg = self.mw_load_interface.get(self)
        self.mw_load_message.set_text(msg)

        self.events.add_timer(event.TimerEvent(LoadTimerEvent, after = 60))

    def mw_load_tick(self, evt):
        self.mw_load_update()
