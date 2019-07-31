# mw_xmms2.py -- display xmms2 track title in the mode window
#
#   Copyright (C) 2008  David H. Bronke <whitelynx@gmail.com>
#   Based on mw_xmms.py, Copyright (C) 2004  Mark Tigges <mtigges@gmail.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""mw_xmms2.py - Display xmms2 track title in the mode window.

This requires xmms2's Python bindings, which live in the xmmsclient module.

"""

from plwm import modewindow, event

try:
    import xmmsclient, os

    XMMS2TimerEvent = event.new_event_type()
    XMMS2ReconnectEvent = event.new_event_type()

    class ModeWindowXMMS2:
        """WM mixin providing an XMMS2 status display in the ModeWindow.

        Example:

        >>> from plwm import mw_xmms2, wmanager, modewindow
        >>> class MyScreen(wmanager.Screen, modewindow.ModeWindowScreen):
        ...     pass
        ... 
        >>> class MyWM(wmanager.WindowManager, mw_xmms2.ModeWindowXMMS2):
        ...     screen_class = MyScreen
        ...     mw_xmms2_position = 0.7
        ...     mw_xmms2_justification = modewindow.RIGHT
        ... 

        """

        mw_xmms2_position = 0.3
        mw_xmms2_justification = modewindow.LEFT

        def __wm_init__(self):
            """Create a mode window message and connect to the XMMS2 server."""
            self.wm_xmms2_message = modewindow.Message(self.mw_xmms2_position,
                self.mw_xmms2_justification)

            self.mw_xmms2_connection = xmmsclient.XMMS("mw_xmms2")
            self.mw_xmms2_connect ()

            for s in self.screens:
                s.modewindow_add_message(self.wm_xmms2_message)

            self.dispatch.add_handler(XMMS2TimerEvent, self.mw_xmms2_tick)
            self.dispatch.add_handler(XMMS2ReconnectEvent, self.mw_xmms2_reconnect)
            self.mw_xmms2_update()


        def mw_xmms2_connect(self):
            """Connect to the XMMS2 server."""
            try:
                self.mw_xmms2_connection.connect(os.getenv("XMMS_PATH"))
            except IOError, detail:
                print "mw_xmms2: Connection failed:", detail


        def mw_xmms2_ms_to_time(self, ms):
            """Convert from milliseconds to a human-readable time format."""
            minutes = ms/1000.0/60
            seconds = (minutes-int(minutes))*60
            return '%d:%02d' % (minutes, seconds)


        def mw_xmms2_update(self):
            """Update the mode window message.
            
            Query the artist and title of the currently-playing tracko and set
            the message accordingly.

            """
            if self.mw_xmms2_connection.get_fd() == -1:
                self.mw_xmms2_connect()
            else:
                result = self.mw_xmms2_connection.playback_current_id()
                result.wait()
                if result.iserror():
                    print "mw_xmms2: playback current id returns error, %s" % result.get_error()

                    self.wm_xmms2_message.set_text("XMMS2 Error: %s" % result.get_error())

                    # There was some problem, so we'll try again in 20 seconds.
                    self.events.add_timer(event.TimerEvent(XMMS2ReconnectEvent, after = 20))

                if result.value() == 0:
                    curstatus = "Stopped"

                else:
                    result = self.mw_xmms2_connection.medialib_get_info(result.value())
                    result.wait()
                    if result.iserror():
                        print "mw_xmms2: medialib get info returns error, %s" % result.get_error()

                        self.wm_xmms2_message.set_text("XMMS2 Error: %s" % result.get_error())

                        # There was some problem, so we'll try again in 20 seconds.
                        self.events.add_timer(event.TimerEvent(XMMS2ReconnectEvent, after = 20))

                    minfo = result.value()
                    try:
                        duration = self.mw_xmms2_ms_to_time(minfo["duration"])
                    except KeyError:
                        duration = "?:??"

                    try:
                        artist = minfo["artist"]
                    except KeyError:
                        artist = "No artist"

                    try:
                        title = minfo["title"]
                    except KeyError:
                        title = "No title"

                    if artist == "No artist" and title == "No title":
                        try:
                            stitle = minfo["file"]
                        except KeyError:
                            stitle = "No file"
                    else:
                        stitle = "%s - %s" % (title, artist)


                    result = self.mw_xmms2_connection.playback_playtime()
                    result.wait()
                    if result.iserror():
                        print "mw_xmms2: playback playtime returns error, %s" % result.get_error()

                        self.wm_xmms2_message.set_text("XMMS2 Error: %s" % result.get_error())

                        # There was some problem, so we'll try again in 20 seconds.
                        self.events.add_timer(event.TimerEvent(XMMS2ReconnectEvent, after = 20))

                    stime = result.value()
                    elapsed = self.mw_xmms2_ms_to_time(stime)


                    result = self.mw_xmms2_connection.playback_status()
                    result.wait()
                    if result.iserror():
                        print "mw_xmms2: playback status returns error, %s" % result.get_error()

                        self.wm_xmms2_message.set_text("XMMS2 Error: %s" % result.get_error())

                        # There was some problem, so we'll try again in 20 seconds.
                        self.events.add_timer(event.TimerEvent(XMMS2ReconnectEvent, after = 20))

                    status = "Unknown"
                    statnum = result.value()
                    if statnum == xmmsclient.PLAYBACK_STATUS_STOP:
                        status = "Stopped"
                    elif statnum == xmmsclient.PLAYBACK_STATUS_PLAY:
                        status = "Playing"
                    elif statnum == xmmsclient.PLAYBACK_STATUS_PAUSE:
                        status = "Paused"

                    # Format the message
                    if status == "Stopped":
                        curstatus = '%s <%s>' % (status, stitle)
                    else:
                        curstatus = '%s <%s> [%s/%s]' % (status, stitle, elapsed, duration)

                self.events.add_timer(event.TimerEvent(XMMS2TimerEvent, after = 1))

                self.wm_xmms2_message.set_text(str(curstatus))


        def mw_xmms2_reconnect(self, evt):
            """Reconnect to the XMMS2 server."""
            self.mw_xmms2_connect()
            self.mw_xmms2_update()


        def mw_xmms2_tick(self, evt):
            self.mw_xmms2_update()


except:

    import sys
    sys.stderr.write('mw_xmms2: could not load xmmsclient python module\n')

    class ModeWindowXMMS2:
        """You do not have XMMS2's Python bindings installed.
        
        The XMMS2 Python bindings are required for mw_xmms2.
        """
        pass

def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()

