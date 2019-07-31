#
# mouse.py -- Basic mouse event handling
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


# WARNING:
#
# This module has been cobbled together using the keys module and an almost
# complete lack of understanding of X internals.  Some of the comments may
# sound irreverent, or you may feel disgust that this looks like such a hack.
# Sorry, please let me know of any problems you find.  I'd love to make it
# robust ... it works for me, hopefully it will work for you. If it doesn't
# hopefully we can fix it!
#
# mtigges@gmail.com
#
# TODO:
#
# 1. Provide support for multiple mouse buttons down at once, the
#    buttonsym thing might have to be completely reworked.
#
# 2. Figure out why there is always a pause before the event reaches
#    _mouseevent.  This doesn't happen in keys, so I'm very curious
#    what's causing it.  There seems to be a second long timer that is
#    polling events in a loop in the dispatcher ... but it's the same
#    beast that the keys system uses, so I'm confused about this.

from Xlib import X, XK
import string
import wmanager
import event
import time

from keys import modifiers, ReleaseModifier

# These are organized like this so that idx%8 gives the same value
# as the X.Button? codes
# The L,R,M are just synonyms for B1,B2,B3 and are transformed to
# those numbers in the string_to_buttonsym function
buttonsyms = ['B1Down',
              'B2Down',
              'B3Down',
              'B4Down',
              'B5Down',
              'LDown',
              'MDown',
              'RDown',
              'B1Up',
              'B2Up',
              'B3Up',
              'B4Up',
              'B5Up',
              'LUp',
              'MUp',
              'RUp',
              'B1Move',
              'B2Move',
              'B3Move',
              'B4Move',
              'B5Move',
              'LMove',
              'MMove',
              'RMove']



def string_to_buttonsym(str):
    try:
        idx = buttonsyms.index(str)

        # this silly looking arithmetic switches any L* to B1* and
        # similary for the R* and M* symbols.
        return 8*(idx/8) + (idx%8)%5 + 1
    except:
        return None

def hash_mousecode(sym,mods):
    return mods<<8 | sym

# This is now the real grabbing class
class MousegrabManager:

    # The MouseHandler class instantiates this class as many times as it
    # needs to ... depending on how you initialize it.  You  shouldn't
    # need to instantiate this guy.

    def __init__(self, wm, window):
        self.wm = wm
        self.window = window
        self.grabs = {}

    def ungrab_buttons(self, mouselist):
        """Ungrab some mouse buttons

        MOUSELIST is a list of (mousecode, modifier) tuples.
        """
        for buttonsym, modifiers in mouselist:
            h = hash_mousecode(buttonsym, modifiers)
            c = self.grabs.get(h, 0)
            if c > 0:
                if c == 1:
                    del self.grabs[h]
                    self.window.ungrab_mouse(buttonsym,
                                             modifiers & ~ReleaseModifier)
                else:
                    self.grabs[h] = self.grabs[h] - 1

    def grab_buttons(self, mouselist):
        """Grab some mouse buttons

        MOUSELIST is a list of (mousecode, modifier) tuples.
        """

        grabs = {}

        for buttonsym, modifiers in mouselist:
            h = hash_mousecode(buttonsym, modifiers)
            c = self.grabs.get(h, 0)
            if c == 0:
                button = buttonsym%8
                mask = buttonsym/8

                if mask==0:
                    mask = X.ButtonPressMask
                elif mask==1:
                    mask = X.ButtonReleaseMask
                else:
                    mask = X.ButtonMotionMask

                try:
                    mask |= grabs[hash_mousecode(button,modifiers)][2]
                except:
                    pass

                grabs[hash_mousecode(button,modifiers)] = (button,
                                                           modifiers,
                                                           mask)

                self.grabs[h] = 1
            else:
                self.grabs[h] = self.grabs[h] + 1

            for k in grabs.keys():
                button,modifiers,mask = grabs[k]
                self.window.grab_button(button,
                                        modifiers,
                                        True,
                                        mask,
                                        X.GrabModeAsync,
                                        X.GrabModeAsync,
                                        X.NONE,
                                        X.NONE,
                                        None)


    def grab_pointer(self, time):
        s = self.window.grab_pointer(0, X.GrabModeAsync, X.GrabModeAsync, time)
        if s != X.GrabSuccess:
            raise error, s

    def ungrab_pointer(self):
        self.wm.display.ungrab_pointer(X.CurrentTime)

class MouseHandler:


    """This class allows you to get mouse events in the same way that
    the keys module allows you to get key presses.  The modifiers on the
    methods are identical.  The different buttons are:

    LDown LMove LUp          left button
    MDown MMove MUp          middle button
    RDown RMove RUp          right button

    You can alternatively use B1 ... B5 for the different buttons.  B1,B2,B3
    correspond to left,middle,right.

    So, as an example the member method named:

      C_M_LDown

    will get left button mouse down events when control and alt are pressed.
    I haven't tested with all combinations, but hopefully it works.

    mtigges@gmail.com


    Unfortunately, at this time there is NO SUPPORT for events with multiple
    mouse buttons down, don't even try it, it won't work.  Sorry.  Fix it if
    you like.
    """

    propagate_mouse = 1
    timeout = None

    def __init__(self, obj):

        # The object can be a window manager, a screen or a window ... just
        # like keys.  What happens depends on that.
        # The vast majority of my testing has been on passing a WindowManager
        # so  ... your mileage may vary on the others.  Please, go ahead
        # and try it and let me know if it needs work.

        if isinstance(obj, wmanager.WindowManager):
            wm = obj
            grabmgrs = []
            for s in obj.screens:
                if not hasattr(s, 'mousegrab_mgr'):
                    s.mousegrab_mgr = MousegrabManager(obj, s.root)
                grabmgrs.append(s.mousegrab_mgr)

        elif isinstance(obj, wmanager.Screen):
            wm = obj.wm
            if not hasattr(obj, 'mousegrab_mgr'):
                obj.mousegrab_mgr = MousegrabManager(obj.wm, obj.root)
            grabmgrs = [obj.mousegrab_mgr]

        elif isinstance(obj, wmanager.Window):
            wm = obj.wm
            if not hasattr(obj, 'keygrab_mgr'):
                obj.mousegrab_mgr = MousegrabManager(obj.wm, obj.window)
            grabmgrs = [obj.mousegrab_mgr]

        else:
            raise TypeError('expected WindowManager, Screen or Client object')

        # Dig through all names in this object, ignoring those beginning with
        # an underscore.

        # First collect all method names in this and it's base classes
        names = {}
        c = [self.__class__]
        while len(c):
            names.update(c[0].__dict__)
            c = c + list(c[0].__bases__)
            del c[0]

        # And now parse the names
        rawbinds = []
        for name in names.keys():
            if name[0] != '_':

                # Find modifiers in name
                mask = 0
                parts = string.split(name, '_')
                while len(parts) >= 2 and modifiers.has_key(parts[0]):
                    mask = mask | modifiers[parts[0]]
                    del parts[0]

                    if len(parts)==1:
                        buttonsym = string_to_buttonsym(parts[0])
                        if buttonsym != None:
                            rawbinds.append((buttonsym,mask,
                                             getattr(self,name)))

        self.wm = wm
        self.dispatch = obj.dispatch
        self.grabmgrs = grabmgrs
        self.rawbindings = rawbinds
        self.grabs = []

        # Add handlers
        if self.propagate_mouse:
            # This is where you want to be ... it will result in only
            # those mouse events you care about triggering the _mouseevent
            # method, everything else will fall through to the apps.
            self.dispatch.add_handler(X.ButtonPress,
                                      self._mouseevent, handlerid = self)
            self.dispatch.add_handler(X.ButtonRelease,
                                      self._mouseevent, handlerid = self)
            self.dispatch.add_handler(X.MotionNotify,
                                      self._mouseevent, handlerid = self)
        else:
            # I left this part in from the keys module, but I think it's
            # a really bad idea.  I wouldn't use this at all.  Bout the
            # only time I could think of using it is if you're writing a
            # system for just one program ... maybe dedicating a laptop
            # to a single purpose ... like mp3 player or something.
            self.dispatch.add_grab_handler(X.ButtonPress,
                                           self._mouseevent, handlerid = self)
            self.dispatch.add_grab_handler(X.ButtonRelease,
                                           self._mouseevent, handlerid = self)
            self.dispatch.add_grab_handler(X.MotionNotify,
                                           self._mouseevent, handlerid = self)

        if self.timeout:
            self.last_mouse_time = None
            self.timer_id = event.new_event_type()
            self.timer = event.TimerEvent(self.timer_id, after = self.timeout)
            self.wm.events.add_timer(self.timer)
            self.dispatch.add_handler(self.timer_id, self._internal_timeout,
                                      handlerid = self)

        self._buildmap()


    def __del__(self):
        wmanager.debug('mem', 'Freeing keyhandler %s', self)
        self._cleanup()

    def _cleanup(self):
        # Remove all our event handlers
        self.dispatch.remove_handler(self)

        # Ungrab buttons
        self._ungrab()

        # Clear the bindings: essential as elements of this list refers
        # to bound methods of this object, i.e. circular references.
        self.rawbindings = None
        self.bindings = None

        # Unscedule any pending timeout
        if self.timeout:
            self.timer.cancel()

    def _grab(self):
        for g in self.grabmgrs:
            g.grab_buttons(self.grabs)

    def _ungrab(self):
        for g in self.grabmgrs:
            g.ungrab_buttons(self.grabs)
        self.grabs = []

    def _buildmap(self):
        """Build mouse bindings mapping.

        Also sets passive grabs for the mouse bindings.
        """
        self.bindings = {}


        # First ungrab the grabs we already have
        self._ungrab()

        # Build up new list of bindings
        for buttonsym, modifiers, func in self.rawbindings:
            self.bindings[hash_mousecode(buttonsym, modifiers)] = func
            self.grabs.append((buttonsym, modifiers))

        # Install the new grabs
        self._grab()

    def _mappingnotify(self, event):
        """Pass as handler for MappingNotify events to rebuild
        the key bindings.
        """
        self._buildmap()

    def _internal_timeout(self, ev):
        """Called when the timer event times out.
        Don't override this, override _timeout instead.
        """

        # Call _timeout if it has been at least self.timeout
        # seconds since the last keypress
        if self.last_mouse_time is None \
           or ev.time - self.last_mouse_time >= self.timeout:
            wmanager.debug('keys', 'timeout, last_mouse = %s, now = %s',
                           self.last_mouse_time, ev.time)
            self._timeout(ev)

        # If not: reschedule a timeout
        else:
            wmanager.debug('mouse', 'rescheduling timeout at %s',
                           self.last_mouse_time + self.timeout)
            self.timer = event.TimerEvent(self.timer_id,
                                          at = self.last_mouse_time + self.timeout)
            self.wm.events.add_timer(self.timer)

    def _timeout(self, event):
        """Called when we really timeout.
        """
        pass

    def _mouseevent(self, event):

        # Store mouse press time (approximate to the current time
        # as the X event.time isn't synced with that)
        self.last_mouse_time = time.time()

        button = event.detail
        state = event.state

        # This function is not nearly as clean as the keys._keyevent, for
        # a couple of reasons ... 1. Mouse events are a little bit different
        # 2. I don't understand all of this well enough to make it really
        # clean, I hacked this all together.


        if button:

            # It seems that if the event.detail field is non-zero it's
            # one of our passive grabs for a press or a release.  The
            # state holds the modifiers+which buttons are down BEFORE
            # the event occured, so if it's a release, we need to get
            # the button mask out of the state before computing the hash.

            state = state & ~(getattr(X,'Button%dMask' % button))

            # Now we have to get the button symbol (for our list above)
            # from the button and the event type
            # We're presuming only one down at a time.
            button = button + (event._code-X.ButtonPress)*8

        else:

            # So, if we're here, it means that the mouse moved.

            if event.state:
                # if it was a non-trivial move (there were modifiers and or
                # mouse buttons down, we come in here.
                for b in [1,2,3,4,5]:
                    # This loop figures out which button is down.
                    # Again, only one at once
                    if event.state&getattr(X,'Button%dMotionMask'%b):
                        button = b
                        break

                #sys.stderr.write('\n')
                #sys.stderr.write('button: %d\n' % button)
                #sys.stderr.write('state : %d\n' % state)

                try:
                    # Again we strip the button mask out to get only the
                    # modifiers.
                    state = state & ~(getattr(X,'Button%dMotionMask' % button))
                except:
                    pass

                #sys.stderr.write('state : %d\n' % state)

                # And convert to an index in our symbols.
                button = button+16


        # Get the hash code for this state
        match = hash_mousecode(button,state)

        # If we have a function for that hash, call it.
        if self.bindings.has_key(match):
            self.bindings[match](event)


class MoveResize(MouseHandler):

    """Simple mouse movement and resize class.  Simply instantiate
    one of these in your windowmanager constructor and voila, you
    can move and resize your windows via your mouse


    Alt+left button will move your window around

    Ctrl+Alt+right button will resize your window (in a preferential dir)

    Alt+middle button will resize your window either horizontally or
               vertically.

    """

    def __init__(self,wm):
        MouseHandler.__init__(self,wm)

    def C_M_LDown(self,evt):
        self.client = self.wm.current_client
        self.dir = None
        if self.client:
            self.mouse_x, self.mouse_y = evt.root_x, evt.root_y

    def C_M_LUp(self,evt):
        self.C_M_LMove(evt)
        self.client = None

    def C_M_LMove(self,evt):
        if self.client:
            c = self.client
            dx,dy = evt.root_x-self.mouse_x, evt.root_y-self.mouse_y
            if self.dir==None:
                if dx<0:
                    if dy<0: self.dir = 0 # left and up
                    if dy>0: self.dir = 3 # left and down
                else:
                    if dy<0: self.dir = 1 # right and up
                    if dy>0: self.dir = 2 # right and down

            if self.dir==0:
                c.configure(x=c.x+dx,y=c.y+dy,
                            width=c.width-dx,height=c.height-dy)
            elif self.dir==1:
                c.configure(x=c.x,y=c.y+dy,
                            width=c.width+dx,height=c.height-dy)
            elif self.dir==2:
                c.configure(x=c.x,y=c.y,
                            width=c.width+dx,height=c.height+dy)
            elif self.dir==3:
                c.configure(x=c.x+dx,y=c.y,
                            width=c.width-dx,height=c.height+dy)
            self.mouse_x = evt.root_x
            self.mouse_y = evt.root_y

    def M_LDown(self,evt):
        self.client = self.wm.current_client
        if self.client:
            self.mouse_x, self.mouse_y = evt.root_x, evt.root_y

    def M_LUp(self,evt):
        self.M_LMove(evt)
        self.client = None

    def M_LMove(self,evt):
        if self.client:
            c = self.client
            dx,dy = evt.root_x-self.mouse_x, evt.root_y-self.mouse_y
            c.configure(x=c.x+dx,y=c.y+dy,width=c.width,height=c.height)
            self.mouse_x = evt.root_x
            self.mouse_y = evt.root_y

    def M_MDown(self,evt):
        self.client = self.wm.current_client
        self.dir = None
        if self.client:
            self.mouse_x, self.mouse_y = evt.root_x, evt.root_y

    def M_MUp(self,evt):
        self.M_MMove(evt)
        self.client = None

    def M_MMove(self,evt):
        if self.client:
            c = self.client
            dx,dy = evt.root_x-self.mouse_x, evt.root_y-self.mouse_y
            if self.dir==None:
                if abs(dx)>abs(dy):
                    if dx<0: self.dir = 3
                    else: self.dir = 1
                elif abs(dy)>abs(dx):
                    if dy<0: self.dir = 0
                    else: self.dir = 2

            if self.dir!=None:
                if self.dir==0:
                    c.configure(x=c.x,y=c.y+dy,
                                width=c.width,height=c.height-dy)
                elif self.dir==1:
                    c.configure(x=c.x,y=c.y,
                                width=c.width+dx,height=c.height)
                elif self.dir==2:
                    c.configure(x=c.x,y=c.y,
                                width=c.width,height=c.height+dy)
                elif self.dir==3:
                    c.configure(x=c.x+dx,y=c.y,
                                width=c.width-dx,height=c.height)
            self.mouse_x = evt.root_x
            self.mouse_y = evt.root_y
