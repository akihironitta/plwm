#
# deltamove.py -- Calculate movement acceleration
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

import sys
from Xlib import X

class DeltaMove:
    """Class to handle increasing (or decreasing) movements for e.g.
    mouse warping.

    Call the method get with a timestamp, and if the time is within a
    timeout (in milliseconds) from the last timestamp passed to get a
    movement length is calculated from the last.  If the timeout has
    expired the movement length is decreased with factor the number of
    times the timeout was missed.

    The movement must be within a minimum and a maximum bound.

    The new movement length is calculated by multiplying the last movement
    with a factor (which can be less than one for decreasing lengths).

    The timestamp will wrap around once each 49.7 day, approximately.
    I'm not worried.
    """

    def __init__(self, initstep = 1, minstep = 1, maxstep = 64,
                 factor = 2, timeout = 200):
        self.time = -sys.maxint
        self.delta = initstep
        self.init = initstep
        self.min = minstep
        self.max = maxstep
        self.factor = factor
        self.timeout = timeout

    def get(self, time = X.CurrentTime):
        if time == X.CurrentTime:
            self.delta = self.init
            self.time = -sys.maxint
            return self.delta

        # At wraparound, and possibly at startup, we can get a overflow
        # error.  I can't be bothered to figure out exactly how to avoid
        # this, so just ignore it and reset the delta.
        try:
            if time >= self.time and time - self.time < self.timeout:
                self.delta = self.delta * self.factor;
            else:
                self.delta = self.delta / pow(float(self.factor),
                                              (time - self.time) / self.timeout);
        except OverflowError:
            self.delta = self.init

        self.delta = int(max(self.min, min(self.delta, self.max)))
        self.time = time

        return self.delta

