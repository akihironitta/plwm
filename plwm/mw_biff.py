#
# mw_biff.py -- new mail notification in a ModeWindow
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

from stat import *
import os
import sys

from plwm import modewindow, event

BiffEventType = event.new_event_type()


# wm mixin
class ModeWindowBiff:
    mw_biff_position = 0.0
    mw_biff_justification = modewindow.LEFT

    mw_biff_mail_message = 'Mail'
    mw_biff_new_mail_message = 'New mail'

    def __wm_init__(self):
        try:
            self.mw_biff_mailpath = os.environ['MAIL']
        except KeyError:
            sys.stderr.write('%s: $MAIL not set, mw_biff disabled\n' % sys.argv[0])
            return

        self.mw_biff_mailp = 0

        self.mw_biff_mailmsg = self.rdb_get('.modewindow.mail.text',
                                    '.ModeWindow.Mail.Text',
                                    self.mw_biff_mail_message)

        self.mw_biff_newmsg = self.rdb_get('.modewindow.newMail.text',
                                           '.ModeWindow.NewMail.Text',
                                           self.mw_biff_new_mail_message)

        self.mw_biff_message = modewindow.Message(self.mw_biff_position,
                                                  self.mw_biff_justification)
        for s in self.screens:
            s.modewindow_add_message(self.mw_biff_message)

        self.dispatch.add_handler(BiffEventType, self.mw_biff_tick)

        self.mw_biff_update()

    def mw_biff_update(self):
        text, ding = self.mw_biff_check_mail()
        self.mw_biff_update_message(text, ding)

        # Trig a timer to recheck in 15 seconds
        self.events.add_timer(event.TimerEvent(BiffEventType, after = 15))

    def mw_biff_update_message(self, text, ding):
        if text is not None:
            self.mw_biff_message.set_text(text)

            if ding:
                self.display.bell(50)

    def mw_biff_check_mail(self):
        try:
            s = os.stat(self.mw_biff_mailpath)
            if S_ISREG(s[ST_MODE]) and s[ST_SIZE] > 0:
                if s[ST_MTIME] >= s[ST_ATIME] or s[ST_CTIME] >= s[ST_ATIME]:
                    mailp = 2
                else:
                    mailp = 1
            else:
                mailp = 0
        except os.error:
            mailp = 0

        if mailp != self.mw_biff_mailp:
            self.mw_biff_mailp = mailp
            if self.mw_biff_mailp == 0:
                return '', 0
            elif self.mw_biff_mailp == 1:
                return self.mw_biff_mailmsg, 0
            else:
                return self.mw_biff_newmsg, 1
        else:
            return None, 0

    def mw_biff_tick(self, evt):
        self.mw_biff_update()

class ThreadedModeWindowBiff(ModeWindowBiff):

    """This is a version of ModeWindowBiff that operates on the
    mailspool in a separate thread.  The point of this is to make sure
    that the entire PLWM doesn't lock up when NFS does that.  It is
    recommended to use this if you mailspool is NFS-mounted.
    """

    def __wm_init__(self):
        # Attribute used to synchronise main PLWM thread
        # with mail check thread.  We use the property of
        # Python threading that thread-switching is only done
        # between atomic Python instructions to avoid having
        # to deal with locks too.

        # And no, PLWM is absolutely not thread safe, thats why the
        # mail checking thread doesn't change the message by itself.

        self.mw_biff_set_message = None
        ModeWindowBiff.__wm_init__(self)

    def mw_biff_update(self):

        # A thread is working on checking that pesky mail
        # Sleep some more.
        if self.mw_biff_set_message == ():
            self.events.add_timer(event.TimerEvent(BiffEventType, after = 15))

        # If a mail check thread has finished, display
        # the message, if any, and reschedule a tick
        elif self.mw_biff_set_message:
            text, ding = self.mw_biff_set_message
            self.mw_biff_update_message(text, ding)

            self.mw_biff_set_message = None
            self.events.add_timer(event.TimerEvent(BiffEventType, after = 12))

        # Else its time to start a new thread
        elif self.mw_biff_set_message is None:
            import thread

            # Indicate that we're working on it
            self.mw_biff_set_message = ()

            thread.start_new_thread(self.mw_biff_start_check, ())

            # Give the other thread three seconds to check for new mail.
            # If it takes longer than that, we're probably having NFS problems.

            self.events.add_timer(event.TimerEvent(BiffEventType, after = 3))

    def mw_biff_start_check(self):
        # Store real info when that has been recieved
        self.mw_biff_set_message = self.mw_biff_check_mail()

