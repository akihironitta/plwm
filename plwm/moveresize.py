#
# moveresize.py -- Move and resize clients
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
import deltamove
import wmanager

class MoveResize:
    def __init__(self, client, delta = deltamove.DeltaMove()):
        """Start to move/resize CLIENT.

        If moveunits() will be used DELTA should be a DeltaMove
        object to use for getting lengths.  If not provided, a
        default DeltaMove will be used.
        """
        self.client = client
        self.delta = delta
        (self.x, self.y, self.width, self.height,
         self.borderwidth) = self.client.geometry()

        # Handle windows who want incremental resizing
        self.req_width = self.width
        self.req_height = self.height
        self.inc_width, self.inc_height = self.client.resize_increment()

        # Capture the pointer position
        ptrpos = self.client.pointer_position()
        if ptrpos:
            self.ptrx, self.ptry = ptrpos
            if self.ptrx < -self.borderwidth or self.ptry < -self.borderwidth \
               or self.ptrx >= self.width + self.borderwidth \
               or self.ptry >= self.height + self.borderwidth:
                self.ptrx, self.ptry = None, None
        else:
            self.ptrx, self.ptry = None, None

        self.client.wm.events.put_event(MoveResizeStart(self.client))

    def setposition(self,x,y):
        # Sets the position to an absolute location, not relative
        self.x, self.y = x,y
        self.adjust()
        self.do()

    def move(self, x, y):
        self.x = self.x + x
        self.y = self.y + y
        self.adjust()
        self.do()

    def resize(self, x, y, width, height):
        """Resize and move client pixelbased."""
        self.x = self.x + x
        self.y = self.y + y
        self.req_width = self.req_width + width
        self.req_height = self.req_height + height
        self.adjust()
        self.do()

    def resizeunits(self, x, y, width, height, time = X.CurrentTime):
        """Resize and move client based on units."""
        d = None
        if x or width:
            if self.inc_width and self.inc_width > 1:
                self.x = self.x + x * self.inc_width
                self.req_width = self.width + width * self.inc_width
            else:
                d = self.delta.get(time)
                self.x = self.x + x * d
                self.req_width = self.req_width + width * d
        if y or height:
            if self.inc_height and self.inc_height > 1:
                self.y = self.y + y * self.inc_height
                self.req_height = self.height + height * self.inc_height
            else:
                if d is None:
                    d = self.delta.get(time)
                self.y = self.y + y * d
                self.req_height = self.req_height + height * d
        self.adjust()
        self.do()

    def adjust(self):
        self.width, self.height = \
                    self.client.follow_size_hints(self.req_width, self.req_height)

        self.x, self.y, self.width, self.height = \
                self.client.keep_on_screen(self.x, self.y,
                                           self.width, self.height)

    def do(self):
        self.client.wm.events.put_event(MoveResizeDo(self.client, self.x, self.y,
                                                     self.width, self.height))

    def end(self):
        if self.ptrx is not None and self.ptrx < self.width + self.borderwidth \
           and self.ptry < self.height + self.borderwidth:
            self.client.warppointer(self.ptrx, self.ptry)

        self.client.wm.events.put_event(MoveResizeEnd(self.client))
        self.client = None

    def abort(self):
        self.client.wm.events.put_event(MoveResizeAbort(self.client))
        self.client = None

class MoveResizeOpaque(MoveResize):
    def do(self):
        MoveResize.do(self)
        self.client.moveresize(self.x, self.y, self.width, self.height)

class MoveResizeOutline(MoveResize):
    def __init__(self, client, delta = deltamove.DeltaMove()):
        MoveResize.__init__(self, client, delta)
        self.outline_show()

    def outline_show(self):
        w = self.width + 2 * self.borderwidth
        h = self.height + 2 * self.borderwidth
        self.client.outline_show(self.x, self.y, w, h)

    def do(self):
        MoveResize.do(self)
        self.outline_show()

    def end(self):
        self.client.outline_hide()
        self.client.moveresize(self.x, self.y, self.width, self.height)
        MoveResize.end(self)

    def abort(self):
        self.client.outline_hide()
        MoveResize.abort(self)


#
# Events for resizing etc
#

class MoveResizeStart:
    def __init__(self, client):
        self.type = MoveResizeStart
        self.client = client

class MoveResizeDo:
    def __init__(self, client, x, y, w, h):
        self.type = MoveResizeDo
        self.client = client
        self.x = x
        self.y = y
        self.width = w
        self.height = h

class MoveResizeEnd:
    def __init__(self, client):
        self.type = MoveResizeEnd
        self.client = client

class MoveResizeAbort:
    def __init__(self, client):
        self.type = MoveResizeAbort
        self.client = client



#
# KeyHandler template for moving/resizing
#

class MoveResizeKeys(keys.KeyGrabKeyboard):

    """MoveResizeKeys is a template keyhandler for moving/resizing
    clients.  You should subclass it to define your own keybindings.

    MoveResizeKeys defines a number of event handler methods:

      _move_X     Move the client in direction X
      _enlarge_X  Enlarge the client in direction X
      _shrink_X   Shrink the client from direction X

    The direction is one of eight combinations of the four cardinal
    points:  e, ne, n, nw, w, sw, s and se

    Additionally theres two methods for finishing the moveresize:

      _moveresize_end    Finish, actually moving and resizing the client
      _moveresize_abort  Abort, leaving client with its old geometry


    By default outline moveresizing is used with the MoveResizeOutline class.
    This can be changed by redefining the attribute _moveresize_class to
    any subclass of MoveResize.

    A small MoveResizeKeys subclass example:

      class MyMRKeys(MoveResizeKeys):
         _moveresize_class = MoveResizeOpaque

         KP_Left = MoveResizeKeys._move_w
         KP_Right = MoveResizeKeys._move_e
         KP_Up = MoveResizeKeys._move_n
         KP_Down = MoveResizeKeys._move_s

         KP_Begin = MoveResizeKeys._moveresize_end
         Escape = MoveResizeKeys._moveresize_abort


    To activate moveresize, write a keyhandler event method like this in
    your basic keyhandler:

      def KP_Begin(self, evt):
         MyMRKeys(self, evt)

    """

    propagate_keys = 0
    timeout = 20

    _moveresize_class = MoveResizeOutline

    def __init__(self, keyhandler, event):
        # Always initialize the keyhandler, otherwise
        # we'll get problems in the __del__ method.

        try:
            keys.KeyGrabKeyboard.__init__(self, keyhandler.wm, event.time)
        except keys.error, status:
            wmanager.debug('keys', 'Grabbing keyboard failed: %d', status)

        # But: if no client is focused, clean up immediately.  This
        # drops the grab and all event handlers
        if keyhandler.wm.current_client is None:
            self._cleanup()

        # Otherwise initialise a MoveResize object for the client
        else:
            wmanager.debug('keys', 'Entering move-resize mode')
            self.delta = deltamove.DeltaMove()
            self.mv = self._moveresize_class(keyhandler.wm.current_client,
                                             self.delta)

    def _move_w(self, event):
        self.mv.move(-self.delta.get(event.time), 0)

    def _move_e(self, event):
        self.mv.move(self.delta.get(event.time), 0)

    def _move_n(self, event):
        self.mv.move(0, -self.delta.get(event.time))

    def _move_s(self, event):
        self.mv.move(0, self.delta.get(event.time))

    def _move_nw(self, event):
        d = self.delta.get(event.time)
        self.mv.move(-d, -d)

    def _move_sw(self, event):
        d = self.delta.get(event.time)
        self.mv.move(-d, d)

    def _move_ne(self, event):
        d = self.delta.get(event.time)
        self.mv.move(d, -d)

    def _move_se(self, event):
        d = self.delta.get(event.time)
        self.mv.move(d, d)

    def _enlarge_w(self, event):
        self.mv.resizeunits(-1, 0, 1, 0, event.time)

    def _enlarge_e(self, event):
        self.mv.resizeunits(0, 0, 1, 0, event.time)

    def _enlarge_n(self, event):
        self.mv.resizeunits(0, -1, 0, 1, event.time)

    def _enlarge_s(self, event):
        self.mv.resizeunits(0, 0, 0, 1, event.time)

    def _enlarge_nw(self, event):
        self.mv.resizeunits(-1, -1, 1, 1, event.time)

    def _enlarge_sw(self, event):
        self.mv.resizeunits(-1, 0, 1, 1, event.time)

    def _enlarge_ne(self, event):
        self.mv.resizeunits(0, -1, 1, 1, event.time)

    def _enlarge_se(self, event):
        self.mv.resizeunits(0, 0, 1, 1, event.time)

    def _shrink_w(self, event):
        self.mv.resizeunits(1, 0, -1, 0, event.time)

    def _shrink_e(self, event):
        self.mv.resizeunits(0, 0, -1, 0, event.time)

    def _shrink_n(self, event):
        self.mv.resizeunits(0, 1, 0, -1, event.time)

    def _shrink_s(self, event):
        self.mv.resizeunits(0, 0, 0, -1, event.time)

    def _shrink_nw(self, event):
        self.mv.resizeunits(1, 1, -1, -1, event.time)

    def _shrink_sw(self, event):
        self.mv.resizeunits(1, 0, -1, -1, event.time)

    def _shrink_ne(self, event):
        self.mv.resizeunits(0, 1, -1, -1, event.time)

    def _shrink_se(self, event):
        self.mv.resizeunits(0, 0, -1, -1, event.time)

    def _moveresize_end(self, event):
        wmanager.debug('keys', 'Leaving move-resize mode')
        self.mv.end()
        self._cleanup()


    def _moveresize_abort(self, event):
        wmanager.debug('keys', 'Aborting move-resize mode')
        self.mv.abort()
        self._cleanup()

    _timeout = _moveresize_abort

