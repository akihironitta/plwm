#
# mw_xmms.py -- display xmms track title in the mode window
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

#
# This file provides two mixins.  The first is a mode window display for
# the currently playing XMMS track. The second is a keyboard controllor
# for controlling the XMMS player.
#
# Of course for any of this to be relevant you must have XMMS, and be
# using it.  Further, you have to have the PyXMMS module.  If you
# don't this module won't cause your WM to crash if you use it, it
# just won't do anything.
#
# This has been developed using PyXMMS-2.03
#   http://people.via.ecp.fr/~flo/

from plwm import modewindow, event, wmanager, keys

try:
    import xmms

    XMMSTimerEvent = event.new_event_type()

    class ModeWindowXMMS:

        # These values are so that the XMMS position appears just
        # to the right of the default output of the mw_load mixin.
        mw_xmms_position = 0.070
        mw_xmms_justification = modewindow.LEFT

        def __wm_init__(self):

            self.wm_xmms_message = modewindow.Message(self.mw_xmms_position,
                                                      self.mw_xmms_justification)

            for s in self.screens:
                s.modewindow_add_message(self.wm_xmms_message)

                self.dispatch.add_handler(XMMSTimerEvent,self.mw_xmms_tick)
                self.mw_xmms_update()

        def mw_xmms_update(self):
            try:
                stime = xmms.get_output_time()
                stitle = xmms.get_playlist_title(xmms.get_playlist_pos())

                if stitle:
                    minutes = stime/1000.0/60
                    seconds = (minutes-int(minutes))*60

                    # Format the message
                    self.wm_xmms_message.set_text('%s %d:%02d' %
                                                  (stitle,
                                                   minutes,seconds))
                self.events.add_timer(event.TimerEvent(XMMSTimerEvent,
                                                       after = 1))
            except:
                # There was some problem, so we'll try again in 20 seconds.
                self.events.add_timer(event.TimerEvent(XMMSTimerEvent,
                                                       after = 20))
                import traceback
                traceback.print_exc()

        def mw_xmms_tick(self,evt):
            self.mw_xmms_update()


    class XMMSKeys(keys.KeyGrabKeyboard):

        # This class provides the keyboard control of xmms
        # I add the followin in my main keyboard class in my window
        # manager:
        #
        #                 def M_m(self, evt):
        #             XMMSKeys(self,evt)
        #
        # With that function the following key controls affect XMMS
        #
        #    Alt+M,P       Pause/Play
        #    Alt+M,S       Stop
        #    Alt+M,Right   Next track
        #    Alt+M,Left    Previous track
        #    Alt+M,Up*     Increase volume
        #    Alt+M,Down*   Decrease volume
        #
        # With the volume changers the grab does not end, so you can
        # repeatedly press Up (or hold it down).  Pressing Return when
        # you are done will release the keyboard grab.
        #

        propagate_keys = 0
        timeout = 4

        def __init__(self, keyhandler, evt):
            keys.KeyGrabKeyboard.__init__(self, keyhandler.wm, evt.time)

        def done(self):
            self._cleanup()

        def M_p(self,evt):
            if xmms.is_playing():
                xmms.pause()
            else:
                xmms.play()
            self.done()

        def M_s(self,evt):
            xmms.stop()
            self.done()

        def M_Right(self,evt):
            xmms.playlist_next()
            self.done()

        def M_Left(self,evt):
            xmms.playlist_prev()
            self.done()

        def M_Up(self,evt):
            xmms.set_main_volume(xmms.get_main_volume()+1)

        def M_Down(self,evt):
            xmms.set_main_volume(xmms.get_main_volume()-1)

        def Return(self,evt): self.done()

        def _timeout(self, evt):
            self.wm.display.bell(100)
            self._cleanup()

        Any_g = _timeout
        Any_Escape = _timeout

except:

    import sys
    sys.stderr.write('mw_xmms: could not load XMMS python module\n')

    class ModeWindowXMMS:
        pass

    class XMMSKeys:
        pass
