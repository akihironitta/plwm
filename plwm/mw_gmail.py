#
# mw_gmail.py -- display gmail info in the mode window
#
#    Copyright (C) 2004  Mark Tigges mtigges@gmail.com
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



import os
from plwm import modewindow, event, wmanager, keys
from gmailconstants import *
try:
    import libgmail

    GMAILTimerEvent = event.new_event_type()

    class ModeWindowGmail:

        # To use this mix-in, create a ~/.mw_gmailrc file.
        # The first line should be your account name, the second
        # your password ... and make sure the file is only user
        # readable, if you want to be secure.

        mw_gmail_position = 0.01
        mw_gmail_justification = modewindow.LEFT

        def __wm_init__(self):

            self.wm_gmail_message = modewindow.Message(self.mw_gmail_position,
                                                      self.mw_gmail_justification)
            try:
                conf = file('%s/.mw_gmailrc' % os.environ['HOME'],'r')
                lines = conf.readlines()
                conf.close()

                self.account = lines[0].strip()
                self.password = lines[1].strip()

                for s in self.screens:
                    s.modewindow_add_message(self.wm_gmail_message)

                    self.dispatch.add_handler(GMAILTimerEvent,
                                              self.mw_gmail_tick)
                    self.mw_gmail_update()
            except:
                sys.stderr.write('mw_gmail: no %s/.mw_gmailrc file found\n'
                                 % os.environ['HOME'])
                import traceback
                traceback.print_exc()

        def getInboxMsgCount(self,ga):
            # For some silly reason, not all the queries are implemented
            # in member funcionts, so we have to add this function.
            items = ga._parseSearchResult(U_QUERY_SEARCH,
                                          q = "is:" + U_AS_SUBSET_INBOX)
            return items[D_THREADLIST_SUMMARY][TS_TOTAL_MSGS]


        def mw_gmail_update(self):
            try:

                ga = libgmail.GmailAccount(self.account,self.password)
                ga.login()

                #result = ga.getMessagesByFolder('inbox', True)
                unread = ga.getUnreadMsgCount()
                inbox = self.getInboxMsgCount(ga)

                # Format the message
                self.wm_gmail_message.set_text('%d/%d' % (unread,inbox))
            except:
                import traceback
                traceback.print_exc()
                self.wm_gmail_message.set_text('N.A.')

            # Check again in 10 minutes.
            self.events.add_timer(event.TimerEvent(GMAILTimerEvent,
                                                   after = 600))

        def mw_gmail_tick(self,evt):
            self.mw_gmail_update()


except:

    import sys
    sys.stderr.write('mw_gmail: could not load libgmail python module\n')
    sys.stderr.write('          see: http://libgmail.sourceforge.net/\n')

    class ModeWindowGmail:
        pass

