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
import errno

TimerEventType = event.new_event_type()


class WatchedFile:
    """Watch FILE.

    When it is present, display PRESENT_MSG in the mode window.  If
    FORMAT_CONTENT is true (default is false) PRESENT_MSG should
    include a %s format code which will be replaced with the stripped
    contents of the file.

    When file does not exist, MISSING_MSG is displayed.  It defaults
    to an empty string.

    If content_re is not None, content_re.search(content) must be true
    for the file to be considered present.
    """

    def __init__(self, file, present_msg = '', format_content = 0,
                 missing_msg = '', content_re = None):
        self.file = file
        self.present_msg = present_msg
        self.format_content = format_content
        self.missing_msg = missing_msg
        self.content_re = content_re

    def update(self):
        """Called by ModeWindowWatchFiles to check for changes to
        files.  Should return the current message.
        """
        if os.path.exists(self.file):
            if self.format_content or self.content_re is not None:
                try:
                    content = open(self.file).read(2048) # be somewhat sensible...
                except IOError, e:
                    return "can't read %s: %s" % (
                        self.file,
                        errno.errorcode.get(e.errno, 'unknown error'))

                if self.content_re is not None:
                    m = self.content_re.search(content)
                    if not m:
                        return self.missing_msg

                if self.format_content:
                    return self.present_msg % content.strip()

            return self.present_msg
        else:
            return self.missing_msg


class ModeWindowWatchFiles:
    """WindowManager mixin: Watch a number of files and display a mode
    window message depending on their existance and contents.

    mw_watchfiles is a list of WatchedFile objects.
    mw_watchfiles_interval is the recheck interval in seconds.
    """
    mw_watchfiles_position = 0.7
    mw_watchfiles_justification = modewindow.RIGHT

    mw_watchfiles = None
    mw_watchfiles_interval = 5

    def __wm_init__(self):
        if not self.mw_watchfiles:
            sys.stderr.write('mw_watchfiles: no files to watch, disabling myself')
            return

        self.mw_watchfiles_last_msg = None

        self.mw_watchfiles_message = modewindow.Message(self.mw_watchfiles_position,
                                                        self.mw_watchfiles_justification)
        for s in self.screens:
            s.modewindow_add_message(self.mw_watchfiles_message)

        self.dispatch.add_handler(TimerEventType, self.mw_watchfiles_tick)

        self.mw_watchfiles_tick(None)

    def mw_watchfiles_tick(self, evt):
        msgs = []
        for file in self.mw_watchfiles:
            msg = file.update()
            if msg:
                msgs.append(msg)

        msg = '  '.join(msgs)

        if self.mw_watchfiles_last_msg != msg:
            self.mw_watchfiles_last_msg = msg
            self.mw_watchfiles_message.set_text(msg)

        self.events.add_timer(event.TimerEvent(TimerEventType, after = self.mw_watchfiles_interval))
