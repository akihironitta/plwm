#
#    event.py -- event handling framework
#
#    Copyright (C) 1999-2001,2009  Peter Liljenberg <peter.liljenberg@gmail.com>
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

import types
import time
import select
import errno
import traceback

from Xlib import X


class EventLoopInterrupt(Exception):
    """
    Exception which, by default, terminates
    BottomDispatcher.event_loop() even in exception-catching mode.
    """
    pass


class Dispatcher(object):
    """
    The event processing engine, taking events from a source and
    dispatching them to matching handlers.  Each handler has a
    predicate and the handler matches when the predicate return true.
    The predicate is typically an event filter, constructed with
    classes and functions in the plwm.filters module.


    Handlers can be grouped on some object, and then removed en-masse
    when that object is cleaning up itself.  This object must be
    hashable.

    A good way to use the grouping is to associate all event handlers
    for e.g. a Client object with it, both "core" event handlers and
    handlers in subclasses, mixins and add-ons.  In this way
    Client.withdraw() can call remove_group(self) to clean up
    everything without each add-on having to react to the withdrawing
    and do their own cleanup.


    Within a dispatcher all handlers matching a predicate will be
    called in some undefined order.  If you think you need to enforce
    a specific order among the handlers, that really means that the
    event is refined by the first handlers into a more abstract or
    detailed event for the latter ones.

    This should be handled by having the first handler reacting to the
    "raw" event generating a new "synthetic" event, which the latter
    handlers can handle.


    Dispatchers can be stacked to allow event grabbing.  There is
    always a bottom dispatcher, the default one.  By pushing another
    dispatcher on its top, the new one gets first dibs on any event.
    If some handler in that higher dispatcher matches an event, the
    handlers in any lower dispatcher will not be called.

    Several dispatchers can be stacked on top of each other.  A new
    dispatcher is always added to the top of the stack, but any
    dispatchers but the bottom one can be removed from the stack.
    """

    def __init__(self, lower_dispatcher):
        """
        Dispatcher objects should not be created directly, only through
        the bottom dispatcher's push_new() method.
        """

        self.higher_dispatcher = None
        self.lower_dispatcher = lower_dispatcher

        if lower_dispatcher is not None:
            lower_dispatcher.higher_dispatcher = self

        # For now the trivial implementation:
        # list of (predicate, handler) pairs
        self.handlers = []

        # Map groups to list of (predicate, handler) pairs
        self.groups = {}


    def add_handler(self, handler, predicate, group = None):
        """
        Add HANDLER to be called for all events matching PREDICATE:

        if PREDICATE(event):
            HANDLER(event)

        A single handler can be added for several predicates, but it
        is often easier to use filters.Or to handle that case.

        If a handler and predicate pair is added more than once, the
        subsequent attempts will be ignored.

        If GROUP isn't None, the handler will belong to that group.
        """

        item = (predicate, handler)
        if item not in self.handlers:
            self.handlers.append(item)

            if group is not None:
                try:
                    self.groups[group].append(item)
                except KeyError:
                    self.groups[group] = [item]


    def remove_handler(self, handler, predicate = None):
        """
        Remove the previously added HANDLER.  If it was added for
        several predicates all of them will be removed, unless
        PREDICATE is given to identify one of them.

        If the handler isn't known, nothing happens.

        Handlers and predicates are compared for equality and not
        identity when being removed.
        """

        i = 0
        while i < len(self.handlers):
            p2, h2 = item = self.handlers[i]

            if handler == h2 and (predicate is None or predicate == p2):
                del self.handlers[i]

                # Also remove from any groups
                for group_handlers in self.groups.itervalues():
                    try:
                        group_handlers.remove(item)
                    except ValueError:
                        pass
            else:
                i += 1


    def remove_group(self, group):
        """
        Remove all handlers belonging to GROUP, if any, in both
        this dispatcher and the ones on top of it.
        """

        if self.higher_dispatcher is not None:
            self.higher_dispatcher.remove_group(group)
            
        try:
            group_handlers = self.groups[group]
        except KeyError:
            return

        i = 0
        while i < len(self.handlers):
            if self.handlers[i] in group_handlers:
                del self.handlers[i]
            else:
                i += 1
    
        del self.groups[group]


    NO_MATCH = 0
    HANDLED = 1
    HANDLED_WITH_EXCEPTIONS = 2

    def dispatch_event(self, event, catch_exceptions = False,
                       interrupt_exceptions = (KeyboardInterrupt,
                                               EventLoopInterrupt),
                       traceback_file = None):
        """
        Dispatch EVENT to all matching handlers.

        Returns NO_MATCH, a false value, if no handler matched the
        event, and HANDLED, a true value, if one or more did.

        By default exceptions are not caught but propagated by
        aborting the event dispatching.  If CATCH_EXCEPTIONS is true,
        then any exception in a predicate or a handler will be caught
        and a traceback printed on TRACEBACK_FILE or sys.stderr if
        None, but the dispatching will then continue with the next
        matching handler.  In this mode, any exception in the tuple
        INTERRUPT_EXCEPTIONS will immediately terminate the loop and
        propagate.

        If an exception occurred in a handler then
        HANDLED_WITH_EXCEPTIONS, a true value, is returned instead of
        HANDLED.
        """

        # Give higher dispatchers first dib on the event
        if self.higher_dispatcher:
            result = self.higher_dispatcher.dispatch_event(
                event, catch_exceptions,
                interrupt_exceptions, traceback_file)

            if result != Dispatcher.NO_MATCH:
                return result

        # They didn't handle it, so we get a shot at it
        result = Dispatcher.NO_MATCH

        for predicate, handler in self.handlers:
            if catch_exceptions:
                try:
                    c = predicate(event)
                except interrupt_exceptions:
                    raise
                except:
                    traceback.print_exc(file = traceback_file)
                    c = False
                    
            else:
                c = predicate(event)
                
            if c:
                if result == Dispatcher.NO_MATCH:
                    result = Dispatcher.HANDLED

                if catch_exceptions:
                    try:
                        handler(event)
                    except interrupt_exceptions:
                        raise
                    except:
                        traceback.print_exc(file = traceback_file)
                        result = Dispatcher.HANDLED_WITH_EXCEPTIONS
                else:
                    handler(event)

        return result


    def pop(self):
        """
        Remove this dispatcher from the stack.  The bottom
        dispatcher can never be removed.
        """

        if self.lower_dispatcher is None:
            raise RuntimeError('popping already popped dispatcher')

        self.lower_dispatcher.higher_dispatcher = self.higher_dispatcher
        if self.higher_dispatcher is not None:
            self.higher_dispatcher.lower_dispatcher = self.lower_dispatcher
    

class BottomDispatcher(Dispatcher):
    """
    The bottom dispatcher class, which have additional methods for
    building the dispatcher stack and running an event loop.
    """
    
    def __init__(self):
        super(BottomDispatcher, self).__init__(None)


    def pop(self):
        raise RuntimeError('attempting to pop the bottom dispatcher')


    def push_new(self):
        """
        Add a new dispatcher to the top of the stack, and return it.
        """

        # Find top dispatcher
        d = self
        while d.higher_dispatcher is not None:
            d = d.higher_dispatcher

        return Dispatcher(d)
        
        
    def event_loop(self, source, max_no_exceptions = 0,
                   interrupt_exceptions = (KeyboardInterrupt,
                                           EventLoopInterrupt),
                   traceback_file = None):
        """
        Dispatch events from SOURCE, which must be an iterable object,
        as long as it generates any.

        Exceptions are passed through by default, unless
        max_no_exceptions is non-zero.  In this that number of events
        will be allowed to cause exceptions before they terminate the
        loop.  These exceptions are caught and a traceback printed on
        TRACEBACK_FILE or sys.stderr if None.  In this mode, any
        exception in the tuple INTERRUPT_EXCEPTIONS will immediately
        terminate the loop and propagate.
        """

        for event in source:
            r = self.dispatch_event(event,
                                    catch_exceptions = max_no_exceptions > 0,
                                    interrupt_exceptions = interrupt_exceptions,
                                    traceback_file = traceback_file)
            if r == Dispatcher.HANDLED_WITH_EXCEPTIONS:
                max_no_exceptions -= 1
    


class EventMask(object):
    """
    Manage event masks on a window.

    This object keeps track of the number of users of each event mask
    and of the blocking depth.

    Each call can only specify a single event mask, not unions of them.
    """

    def __init__(self, window):
        self.window = window
        self.masks = {}
        self.blocked_masks = {}


    def clear(self, onerror = None):
        self.masks = {}
        self.blocked_masks = {}
        self.window.change_attributes(event_mask = 0, onerror = onerror)


    def set(self, mask, onerror = None):
        """Set the event MASK on the window.
        """

        self.masks[mask] = self.masks.get(mask, 0) + 1
        self.update_window_mask(onerror)


    def unset(self, mask, onerror = None):
        """Unset MASK on the window.
        """

        try:
            rc = self.masks[mask]
        except KeyError:
            raise RuntimeError('mask not set: %s' % mask)

        assert rc > 0
        
        if rc == 1:
            del self.masks[mask]
        else:
            self.masks[mask] = rc - 1

        self.update_window_mask(onerror)


    def block(self, mask, onerror = None):

        """Temporarily block MASK on the window.
        """

        self.blocked_masks[mask] = self.blocked_masks.get(mask, 0) + 1
        self.update_window_mask(onerror)


    def unblock(self, mask, onerror = None):

        """Remove block on MASKS on the window.

        The inverse of EventDispatcher.block_masks().
        """

        try:
            rc = self.blocked_masks[mask]
        except KeyError:
            raise RuntimeError('mask not blocked: %s' % mask)
        
        assert rc > 0

        if rc == 1:
            del self.blocked_masks[mask]
        else:
            self.blocked_masks[mask] = rc - 1

        self.update_window_mask(onerror)


    def update_window_mask(self, onerror):

        """Configure the window mask to reflect any changes.
        """

        mask = 0
        for m in self.masks.iterkeys():
            if not self.blocked_masks.has_key(m):
                mask = mask | m

        self.window.change_attributes(event_mask = mask, onerror = onerror)
    


__next_event_type = 256
def new_event_type():
    """Returns a new event type code.  The code is an integer, unique
    with respect to X event types and other event types allocated
    with new_event_type().
    """

    global __next_event_type
    t = __next_event_type
    __next_event_type = __next_event_type + 1
    return t


class TimerEvent:
    def __init__(self, event_type, after = 0, at = 0):
        self.type = event_type
        if at > 0:
            self.time = at
        else:
            self.time = time.time() + after

    def cancel(self):
        self.time = None

    def str(self):
        if self.time is None:
            return '<%s cancelled>' % self.__class__.__name__
        else:
            return '<%s at %d in %d seconds>' % (self.__class__.__name__, self.time,
                                                 time.time() - self.time)

class FileEvent:
    READ = 1
    WRITE = 2
    EXCEPTION = 4

    def __init__(self, event_type, file, mode = None):
        self.type = event_type
        self.file = file
        if mode is None:
            self.mode = 0
            if 'r' in self.file.mode:
                self.mode = self.mode | FileEvent.READ
            if 'w' in self.file.mode:
                self.mode = self.mode | FileEvent.WRITE
        else:
            self.mode = mode

        self.state = 0
        self.unhandled = 0

    def fileno(self):
        return self.file.fileno()

    def cancel(self):
        self.file = None

    def set_mode(self, newmode = None, set = 0, clear = 0):
        if newmode is not None:
            self.mode = newmode

        self.mode = (self.mode | set) & ~clear

    def str(self):
        if self.file is None:
            return '<%s cancelled>' % self.__class__.__name__
        else:
            mode = ''
            if self.mode & FileEvent.READ:
                mode = mode + 'R'
            if self.mode & FileEvent.WRITE:
                mode = mode + 'W'
            if self.mode & FileEvent.EXCEPTION:
                mode = mode + 'E'

            return '<%s for %s mode %s>' % (self.__class__.__name__, self.file, mode)

class EventFetcher:
    def __init__(self, display):
        self.display = display
        self.timers = []
        self.events = []
        self.x_events = []
        self.files = []

    def iter_events(self):
        """Return an iterator generating events indefinitely."""
        while 1:
            yield self.next_event()


    def next_event(self, timeout = None):
        # If select is interrupted by a signal, we just want to
        # make everything from scratch
        while 1:
            # First return synthetic events
            if self.events:
                e = self.events[0]
                del self.events[0]

                # If e is an FileEvent, move unhandled to event state
                if isinstance(e, FileEvent):
                    e.state = e.unhandled
                    e.unhandled = 0

                return e

            # Return any read but unprocessed X events
            if self.x_events:
                xe = self.x_events[0]
                del self.x_events[0]
                return xe

            # Attempt to read any events, and if there are any return the first
            xe = self._read_x_events()
            if xe:
                return xe

            now = time.time()

            # Normalize negative timeout values
            if timeout is not None and timeout < 0:
                timeout = 0

            to = None
            # See if we have to wait for a timer
            while self.timers:
                te = self.timers[0]

                # Is this timer canceled?
                if te.time is None:
                    del self.timers[0]
                    continue

                to = te.time

                # This timer has already timed out, so return it
                if to <= now:
                    del self.timers[0]
                    return te

                # Is the general event timeout earlier than this timer?
                if timeout is not None and to > (timeout + now):
                    to = timeout + now
                    te = None

                # Break the loop, as we have found a valid timer
                break


            # Do we have a general event timeout?
            if to is None and timeout is not None:
                to = timeout + now
                te = None

            # Loop until we return an event
            while 1:
                # Wait for X data or a timeout
                read = [self.display]
                write = []
                exc = []

                # Iterate over all files, removing closed and cancelled.
                # The other are added to the corresponding lists

                i = 0
                while i < len(self.files):
                    f = self.files[i]

                    # FileEvent has been cancelled
                    if f.file is None:
                        del self.files[i]

                    # Uncancelled file event
                    else:

                        # Try to get the fileno, in an attempt to
                        # find closed but uncancelled files, so we
                        # can remove them.
                        try:
                            f.fileno()
                        except ValueError:
                            del self.files[i]

                        # Seems to be an open file, add it
                        else:

                            # Get the interested, as yet not recieved, modes
                            m = f.mode & ~f.unhandled

                            if m & FileEvent.READ:
                                read.append(f)
                            if m & FileEvent.WRITE:
                                write.append(f)
                            if m & FileEvent.EXCEPTION:
                                exc.append(f)

                            i = i + 1

                # Wrap select() in a loop, so that EINTRS are ignored
                # correctly

                while 1:
                    try:
                        if to is None:
                            readable, writable, excable = select.select(read, write, exc)
                        else:
                            wait = max(to - time.time(), 0)
                            readable, writable, excable = select.select(read, write, exc, wait)
                    except select.error, val:
                        if val[0] != errno.EINTR:
                            raise val
                    else:
                        break

                # We have timed out, return the timer event or None
                if not readable and not writable and not excable:
                    # Delete the timed out timer
                    if te is not None:
                        del self.timers[0]
                        # Don't return canceled timers
                        if te.time is not None:
                            return te

                        # break the inner while loop to find another timer
                        else:
                            break
                    else:
                        return None

                # Iterate over all ready files.  Add all ready
                # FileEvents to the synthetic event list, unless
                # they already are there, and 'or' in the mode

                xe = None

                for f in readable:

                    # By treating the display first, we ensure
                    # that X events are prioritized over file events

                    if f is self.display:
                        xe = self._read_x_events()
                    else:
                        if f.unhandled == 0:
                            self.events.append(f)
                        f.unhandled = f.unhandled | FileEvent.READ

                for f in writable:
                    if f.unhandled == 0:
                        self.events.append(f)
                    f.unhandled = f.unhandled | FileEvent.WRITE

                for f in excable:
                    if f.unhandled == 0:
                        self.events.append(f)
                    f.unhandled = f.unhandled | FileEvent.EXCEPTION

                # If there was an X event, return it immedieately
                if xe is not None:
                    return xe

                # If there was some file event, return it by breaking
                # out of the inner while-loop, so we get back to
                # the top of the function
                if self.events:
                    break

                # Something was recieved, but not an event.  Loop around
                # to select one more time

    def _read_x_events(self):
        # Read as many x events as possible, and return the first one.
        # Store the rest in x_events
        i = self.display.pending_events()
        if i > 0:
            # Store first event to be returned immediately,
            # and put remaining events on the events queue.
            xe = self.display.next_event()
            while i > 1:
                self.x_events.append(self.display.next_event())
                i = i - 1
            return xe
        else:
            return None




    def add_timer(self, timer):
        """Add a TimerEvent TIMER to the event list.
        """

        # We iterate over the entire timer list, to remove cancelled timers

        i = 0
        while i < len(self.timers):
            t = self.timers[i]

            # Remove cancelled timers
            if t.time is None:
                del self.timers[i]
            else:
                # If we haven't already inserted timer, perform checks
                if timer and timer.time < t.time:
                    self.timers.insert(i, timer)
                    i = i + 1
                    timer = None

                i = i + 1

        if timer:
            self.timers.append(timer)

    def add_file(self, file):
        """Add the FileEvent FILE to the list of files to watch.

        FILE will be sent when it is ready for reading or writing, as
        specified by its mode.

        Remove FILE from list of interesting events by calling
        FILE.cancel().
        """
        self.files.append(file)

    def put_event(self, event):
        """Add a synthesized EVENT.
        """
        self.events.append(event)


# A list of X events and their default event masks.

default_event_masks = {
    X.KeyPress: X.KeyPressMask,
    X.KeyRelease: X.KeyReleaseMask,

    X.ButtonPress: X.ButtonPressMask,
    X.ButtonRelease: X.ButtonReleaseMask,
    X.MotionNotify: [X.PointerMotionMask, X.ButtonMotionMask],

    X.EnterNotify: X.EnterWindowMask,
    X.LeaveNotify: X.LeaveWindowMask,

    X.FocusIn: X.FocusChangeMask,
    X.FocusOut: X.FocusChangeMask,

    X.KeymapNotify: X.KeymapStateMask,

    X.Expose: X.ExposureMask,
    X.GraphicsExpose: X.ExposureMask,
    X.NoExpose: X.ExposureMask,

    X.VisibilityNotify: X.VisibilityChangeMask,

    X.CreateNotify: X.SubstructureNotifyMask,

    # The following seven events can also be sent when
    # X.SubstructureNotifyMask is set, but the default
    # has to be considered to the the ordinary
    # X.StructureNotifyMask

    X.DestroyNotify: X.StructureNotifyMask,
    X.UnmapNotify: X.StructureNotifyMask,
    X.MapNotify: X.StructureNotifyMask,
    X.ReparentNotify: X.StructureNotifyMask,
    X.ConfigureNotify: X.StructureNotifyMask,
    X.GravityNotify: X.StructureNotifyMask,
    X.CirculateNotify: X.StructureNotifyMask,

    X.MapRequest: X.SubstructureRedirectMask,
    X.ConfigureRequest: X.SubstructureRedirectMask,
    X.CirculateRequest: X.SubstructureRedirectMask,
    X.ResizeRequest: X.ResizeRedirectMask,

    X.PropertyNotify: X.PropertyChangeMask,

    X.ColormapNotify: X.ColormapChangeMask,

    # The following events have no event mask:
    # X.SelectionClear
    # X.SelectionRequest
    # X.SelectionNotify
    # X.ClientMessage
    # X.MappingNotify
}


class EventHandler:
    def __init__(self, handler, masks, handlerid):
        self.handler = handler
        self.id = handlerid
        self.masks = masks

    def __cmp__(self, obj):
        return cmp(self.id, obj)

    def call(self, eventobj):
        self.handler(eventobj)

    def clear_masks(self, dispatcher):
        if self.masks is not None:
            dispatcher.unset_masks(self.masks)
            self.masks = None

class EventDispatcher:
    def __init__(self):
        self.system_events = {}
        self.grab_events = {}
        self.normal_events = {}


    def handle_event(self, eventobj, systemonly = 0):

        """Dispatch the event EVENTOBJ to all matching handlers.

        If SYSTEMONLY is true, skip calling grab and normal event
        handlers.

        Returns 1 if a grab event handler was called, 0 otherwise.
        """

        # Call all the system event handlers, and then
        # quit if systemonly is true.

        for eh in self.system_events.get(eventobj.type, []):
            eh.call(eventobj)

        if systemonly:
            return 1

        # If there are any grab events for this type,
        # call the last one and then quit.  Otherwise
        # call all the normal event handlers.

        try:
            eh = self.grab_events[eventobj.type][-1]
        except (KeyError, IndexError):
            eh = None

        if eh is not None:
            eh.call(eventobj)
            return 1
        else:
            for eh in self.normal_events.get(eventobj.type, []):
                eh.call(eventobj)
            return 0

    def add_handler(self, event, handler, masks = None, handlerid = None):

        """Add an event handler for this window.

        EVENT is an event type identifier.  This can be one of the
        numeric constants defined in X.py, a string, or any other
        object which can be used as a key in a mapping.

        HANDLER is a function which gets called with a single
        argument: the event object.  All event object has a `type'
        attribute which will have the value of EVENT.

        MASKS can be a tuple or list of X event masks to set on this
        window.  If omitted or None, default masks for this event will
        be set, if any.

        If HANDLERID is provided, it will be an object used to
        identify this handler when calling
        EventDispatcher.remove_handler().  If omitted, HANDLER itself
        will be used.
        """

        self.add_handler_type(self.normal_events, event, handler,
                              masks, handlerid)


    def add_system_handler(self, event, handler, masks = None, handlerid = None):

        """Add a system handler for this window.  The arguments are
        the same as for EventDispatcher.add_handler().

        A system handler will be called before any grab or normal handlers.
        """
        self.add_handler_type(self.system_events, event, handler,
                              masks, handlerid)


    def add_grab_handler(self, event, handler, masks = None, handlerid = None):

        """Add a grab handler for this window.  The arguments are
        the same as for EventDispatcher.add_handler().

        A grab handler will prevent previously added grab handlers and
        any normal handlers from being called.  System handlers will
        be called as normal, however.
        """

        self.add_handler_type(self.grab_events, event, handler,
                              masks, handlerid)


    def add_handler_type(self, dict, event, handler, masks, handlerid):

        """Internal function used to add handlers."""

        if masks is None:
            masks = default_event_masks.get(event, None)

        if handlerid is None:
            handlerid = handler

        eh = EventHandler(handler, masks, handlerid)
        if dict.has_key(event):
            dict[event].append(eh)
        else:
            dict[event] = [eh]

        if masks is not None:
            self.set_masks(masks)


    def remove_handler(self, handlerid):

        """Remove the handler identified by HANDLERID.

        This will also clear any masks this handler has set.
        """

        for dict in self.system_events, self.grab_events, self.normal_events:
            for hs in dict.values():
                ok = 1
                while ok:
                    try:
                        i = hs.index(handlerid)
                    except ValueError:
                        ok = 0
                    else:
                        hs[i].clear_masks(self)
                        del hs[i]

    def set_masks(self, masks, onerror = None):

        """Set MASKS on the window.

        MASKS can either be an X.*Mask constant or a list of such
        constants.
        """
        pass

    def unset_masks(self, masks, onerror = None):

        """Unset MASKS on the window.

        The inverse of EventDispatcher.set_masks().
        """
        pass

    def block_masks(self, masks, onerror = None):

        """Temporarily block MASKS on the window.

        MASKS can either be an X.*Mask constant or a list of such
        constants.
        """
        pass

    def unblock_masks(self, masks, onerror = None):

        """Remove block on MASKS on the window.

        The inverse of EventDispatcher.block_masks().
        """
        pass


class WindowDispatcher(EventDispatcher):
    def __init__(self, event_mask):
        """
        Create an event dispatcher using EVENT_MASK to manage X
        event masks on some window.
        """

        EventDispatcher.__init__(self)

        self.event_mask = event_mask

    def set_masks(self, masks, onerror = None):

        """Set MASKS on the window.

        MASKS can either be an X.*Mask constant or a list of such
        constants.
        """

        if type(masks) is types.IntType:
            self.event_mask.set(masks, onerror = onerror)
        else:
            for m in masks:
                self.event_mask.set(m, onerror = onerror)


    def unset_masks(self, masks, onerror = None):

        """Unset MASKS on the window.

        The inverse of EventDispatcher.set_masks().
        """

        if type(masks) is types.IntType:
            self.event_mask.unset(masks, onerror = onerror)
        else:
            for m in masks:
                self.event_mask.unset(m, onerror = onerror)


    def block_masks(self, masks, onerror = None):

        """Temporarily block MASKS on the window.

        MASKS can either be an X.*Mask constant or a list of such
        constants.
        """

        if type(masks) is types.IntType:
            self.event_mask.block(masks, onerror = onerror)
        else:
            for m in masks:
                self.event_mask.block(m, onerror = onerror)


    def unblock_masks(self, masks, onerror = None):

        """Remove block on MASKS on the window.

        The inverse of EventDispatcher.block_masks().
        """

        if type(masks) is types.IntType:
            self.event_mask.unblock(masks, onerror = onerror)
        else:
            for m in masks:
                self.event_mask.unblock(m, onerror = onerror)


class SlaveDispatcher(EventDispatcher):
    def __init__(self, masters):
        """Create a SlaveDispatcher for MASTERS.

        MASTERS is a list of other EventDispatchers which this class
        will call when setting, clearing, blocking and unblocking masks.
        """

        EventDispatcher.__init__(self)
        # Copy list, since we can modify list later
        self.masters = list(masters)

    def add_master(self, master):
        """Add a master dispatcher to this slave dispatcher.
        """
        self.masters.append(master)

    def set_masks(self, masks, onerror = None):

        """Set MASKS on the window.

        MASKS can either be an X.*Mask constant or a list of such
        constants.
        """
        for m in self.masters:
            m.set_masks(masks, onerror)

    def unset_masks(self, masks, onerror = None):

        """Unset MASKS on the window.

        The inverse of EventDispatcher.set_masks().
        """
        for m in self.masters:
            m.unset_masks(masks, onerror)

    def block_masks(self, masks, onerror = None):

        """Temporarily block MASKS on the window.

        MASKS can either be an X.*Mask constant or a list of such
        constants.
        """
        for m in self.masters:
            m.block_masks(masks, onerror)


    def unblock_masks(self, masks, onerror = None):

        """Remove block on MASKS on the window.

        The inverse of EventDispatcher.block_masks().
        """
        for m in self.masters:
            m.unblock_masks(masks, onerror)



