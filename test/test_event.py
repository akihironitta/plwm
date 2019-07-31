
import sys
import os
import unittest

sys.path[1:1] = [os.path.join(sys.path[0], '..')]

from plwm import event


# Helper objects for the dispatcher test

class Filter(object):
    def __init__(self, evt):
        self.event = evt

    def __call__(self, evt):
        return evt == self.event


class Handler(object):
    def __init__(self):
        self.called = 0
        self.event = None

    def __call__(self, evt):
        self.called += 1
        self.event = evt


class HellRaiser(Handler):
    def __init__(self, exception):
        super(HellRaiser, self).__init__()
        self.exception = exception

    def __call__(self, evt):
        super(HellRaiser, self).__call__(evt)
        raise self.exception()
    
class TestException1(Exception): pass
class TestException2(Exception): pass

class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.d = event.BottomDispatcher()
        self.f1 = Filter(1)
        self.h1 = Handler()
        self.f2 = Filter(2)
        self.h2a = Handler()
        self.h2b = Handler()
        self.r1 = HellRaiser(TestException1)
        self.r2 = HellRaiser(TestException2)
        self.q = HellRaiser(event.EventLoopInterrupt)
        
        self.exception_file = open('caught_exceptions.txt', 'at')

    def test_00_add_handler_once(self):
        self.d.add_handler(self.h1, self.f1)
        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 1)


    def test_01_add_handler_twice(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.h1, self.f1)

        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 1)


    def test_02_dispatch_no_match(self):
        self.d.add_handler(self.h1, self.f1)
        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.NO_MATCH)
        self.assertEqual(self.h1.called, 0)
        self.assertEqual(self.h1.event, None)


    def test_03_add_handler_for_two_filters(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.h1, self.f2)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 2)

        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 2)
        self.assertEqual(self.h1.event, 1)


    def test_04_add_two_handlers_for_same_filter(self):
        self.d.add_handler(self.h2a, self.f2)
        self.d.add_handler(self.h2b, self.f2)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        
        # Both handlers should have gotten the event
        self.assertEqual(self.h2a.called, 1)
        self.assertEqual(self.h2a.event, 2)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)

        
    def test_10_remove_handler(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.h1, self.f2)

        self.d.remove_handler(self.h1)

        # Removed for both filters:
        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.NO_MATCH)
        self.assertEqual(self.h1.called, 0)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.NO_MATCH)
        self.assertEqual(self.h1.called, 0)

        # Safe to do a second time
        self.d.remove_handler(self.h1)


    def test_11_remove_handler_for_filter(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.h1, self.f2)

        self.d.remove_handler(self.h1, self.f1)

        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.NO_MATCH)
        self.assertEqual(self.h1.called, 0)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 2)

        # Safe to do a second time
        self.d.remove_handler(self.h1, self.f1)

        # Remove for other filter too
        self.d.remove_handler(self.h1, self.f2)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.NO_MATCH)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 2)


    def test_12_remove_group(self):
        self.d.add_handler(self.h1, self.f1, 'foo')
        self.d.add_handler(self.h2a, self.f2, 'foo')
        self.d.add_handler(self.h2b, self.f2, 'bar')

        # whitebox: two groups known
        self.assertEqual(len(self.d.groups), 2)

        self.d.remove_group('foo')

        # whitebox: and now one
        self.assertEqual(len(self.d.groups), 1)

        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.NO_MATCH)
        self.assertEqual(self.h1.called, 0)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h2a.called, 0)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)

        
    def test_13_remove_grouped_handler(self):
        self.d.add_handler(self.h1, self.f1, 'foo')
        self.d.add_handler(self.h1, self.f2, 'bar')
        
        self.d.remove_handler(self.h1, self.f2)

        # whitebox: when removing h1,f2 specifically, it should be
        # removed from 'bar' but 'foo' should not be affected since h1
        # in that group has another predicate

        self.assertEqual(len(self.d.groups['bar']), 0)
        self.assertEqual(len(self.d.groups['foo']), 1)
        

    def test_20_exceptions_in_handler(self):
        self.d.add_handler(self.r1, self.f1)
        self.assertRaises(TestException1, self.d.dispatch_event, 1)
        self.assertEqual(self.r1.called, 1)
        self.assertEqual(self.r1.event, 1)

    def test_21_exceptions_in_filter(self):
        self.d.add_handler(self.h1, self.r1)
        self.assertRaises(TestException1, self.d.dispatch_event, 1)
        self.assertEqual(self.h1.called, 0)


    def test_22_catch_exceptions_in_handler(self):
        self.d.add_handler(self.r1, self.f1)
        self.d.add_handler(self.h1, self.f1)

        r = self.d.dispatch_event(1, catch_exceptions = True,
                                  traceback_file = self.exception_file)
        self.assertEqual(r, self.d.HANDLED_WITH_EXCEPTIONS)

        self.assertEqual(self.r1.called, 1)
        self.assertEqual(self.r1.event, 1)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 1)

    def test_23_catch_exceptions_in_filter(self):
        self.d.add_handler(self.h2a, self.r1)
        self.d.add_handler(self.h2b, self.f2)

        # Exceptions in predicate doesn't affect return code
        r = self.d.dispatch_event(1, catch_exceptions = True,
                                  traceback_file = self.exception_file)
        self.assertEqual(r, self.d.NO_MATCH)

        r = self.d.dispatch_event(2, catch_exceptions = True,
                                  traceback_file = self.exception_file)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h2a.called, 0)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)


    def test_30_event_loop(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.h2a, self.f2)
        self.d.add_handler(self.h2b, self.f2)

        self.d.event_loop([1, 1, 2, 1])
        
        self.assertEqual(self.h1.called, 3)
        self.assertEqual(self.h1.event, 1)
        self.assertEqual(self.h2a.called, 1)
        self.assertEqual(self.h2a.event, 2)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)


    def test_31_event_loop_exception(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.r1, self.f2)

        self.assertRaises(TestException1, self.d.event_loop, [1, 1, 2, 1])
        
        self.assertEqual(self.h1.called, 2)
        self.assertEqual(self.h1.event, 1)


    def test_31_event_loop_catch_two_exception(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.r1, self.f2)

        self.assertRaises(TestException1, self.d.event_loop,
                          [1, 1, 2, 1, 2, 1, 1, 2, 1],
                          max_no_exceptions = 2,
                          traceback_file = self.exception_file)
        
        self.assertEqual(self.h1.called, 5)
        self.assertEqual(self.h1.event, 1)


    def test_32_event_loop_interrupt(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.q, self.f2)

        self.assertRaises(event.EventLoopInterrupt, self.d.event_loop,
                          [1, 1, 2, 1],
                          max_no_exceptions = 2,
                          traceback_file = self.exception_file)
        
        self.assertEqual(self.h1.called, 2)
        self.assertEqual(self.h1.event, 1)


    def test_40_pop_bottom_handler_fails(self):
        self.assertRaises(RuntimeError, self.d.pop)


    def test_41_push_dispatcher(self):
        self.d.add_handler(self.h1, self.f1)
        self.d.add_handler(self.h2a, self.f2)

        d2 = self.d.push_new()
        d2.add_handler(self.h2b, self.f2)
        
        r = self.d.dispatch_event(1)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 1)

        # h2b blocks h2a from receiving event
        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h2a.called, 0)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)


    def test_42_push_two_dispatcher(self):
        self.d.add_handler(self.h1, self.f2)

        d2 = self.d.push_new()
        d2.add_handler(self.h2a, self.f2)

        d3 = self.d.push_new()
        d3.add_handler(self.h2b, self.f2)
        
        # h2b blocks h2a and h1 from receiving event
        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 0)
        self.assertEqual(self.h2a.called, 0)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)


    def test_42_pop_top_dispatcher(self):
        self.d.add_handler(self.h1, self.f2)

        d2 = self.d.push_new()
        d2.add_handler(self.h2a, self.f2)

        d3 = self.d.push_new()
        d3.add_handler(self.h2b, self.f2)
        
        d3.pop()
        
        # h2b gone, so h2a blocks h1 from receiving event
        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 0)
        self.assertEqual(self.h2a.called, 1)
        self.assertEqual(self.h2a.event, 2)
        self.assertEqual(self.h2b.called, 0)


    def test_43_pop_middle_dispatcher(self):
        self.d.add_handler(self.h1, self.f2)

        d2 = self.d.push_new()
        d2.add_handler(self.h2a, self.f2)

        d3 = self.d.push_new()
        d3.add_handler(self.h2b, self.f2)
        
        d2.pop()
        
        # h2b gets the event
        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 0)
        self.assertEqual(self.h2a.called, 0)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)

        # and after removing it, h1 gets it instead
        d3.remove_handler(self.h2b)

        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 1)
        self.assertEqual(self.h1.event, 2)
        self.assertEqual(self.h2a.called, 0)
        self.assertEqual(self.h2b.called, 1)
        self.assertEqual(self.h2b.event, 2)


    def test_44_remove_group_from_all_dispatchers(self):
        self.d.add_handler(self.h1, self.f2, 'foo')

        d2 = self.d.push_new()
        d2.add_handler(self.h2a, self.f2, 'bar')

        d3 = self.d.push_new()
        d3.add_handler(self.h2b, self.f2, 'foo')

        self.d.remove_group('foo')

        # whitebox: foo gone, bar remains
        self.assertEqual(len(self.d.groups), 0)
        self.assertEqual(len(d2.groups), 1)
        self.assertEqual(len(d3.groups), 0)

        # h2a thus gets the event
        r = self.d.dispatch_event(2)
        self.assertEqual(r, self.d.HANDLED)
        self.assertEqual(self.h1.called, 0)
        self.assertEqual(self.h2a.called, 1)
        self.assertEqual(self.h2a.event, 2)
        self.assertEqual(self.h2b.called, 0)


# Helper dummy object for EventMask test
class EventMaskWindowDummy(object):
    def __init__(self):
        self.masks = 0

    def change_attributes(self, event_mask = None, onerror = None):
        self.masks = event_mask

class TestEventMask(unittest.TestCase):
    def test_00_set_unset(self):
        w = EventMaskWindowDummy()
        m = event.EventMask(w)

        m.set(1); self.assertEqual(w.masks, 1)
        m.set(2); self.assertEqual(w.masks, 3)
        m.set(1); self.assertEqual(w.masks, 3)

        self.assertRaises(RuntimeError, m.unset, 4)

        m.unset(1); self.assertEqual(w.masks, 3)
        m.unset(1); self.assertEqual(w.masks, 2)
        m.unset(2); self.assertEqual(w.masks, 0)

        self.assertRaises(RuntimeError, m.unset, 1)


    def test_10_block_unblock(self):
        w = EventMaskWindowDummy()
        m = event.EventMask(w)

        m.set(1); m.set(2); self.assertEqual(w.masks, 3)

        m.block(2); self.assertEqual(w.masks, 1)

        m.block(2); self.assertEqual(w.masks, 1)

        self.assertRaises(RuntimeError, m.unblock, 1)

        m.unblock(2); self.assertEqual(w.masks, 1)
        m.unblock(2); self.assertEqual(w.masks, 3)

        m.block(4); self.assertEqual(w.masks, 3)
        m.set(4); self.assertEqual(w.masks, 3)
        m.unblock(4); self.assertEqual(w.masks, 7)

        self.assertRaises(RuntimeError, m.unblock, 4)

        

if __name__ == '__main__':
    try:
        os.unlink('caught_exceptions.txt')
    except OSError:
        pass
    
    unittest.main()

# Local Variables:
# compile-command: "cd ../test; python test_event.py"
# End:
