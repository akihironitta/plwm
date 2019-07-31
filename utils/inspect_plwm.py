#!/usr/bin/env python
#
# inspect_plwm.py -- PLWM inspect client
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

import sys
import os

from Xlib import display, rdb
import readline
import socket
import struct
import string

class InspectError(Exception): pass

class Inspect:
    def __init__(self, disp):

        # Get property containing inspect port and cookie

        self.PLWM_INSPECT_SERVER = disp.intern_atom('_PLWM_INSPECT_SERVER')
        p = disp.screen().root.get_property(self.PLWM_INSPECT_SERVER,
                                            self.PLWM_INSPECT_SERVER,
                                            0, 2)
        if not p or p.format != 32 or len(p.value) != 2:
            raise InspectError('valid _PLWM_INSPECT_SERVER property not found')

        port = int(p.value[0])
        cookie = int(p.value[1])

        # Connect to the same host as the display
        host = string.split(disp.get_display_name(), ':')[0]
        if host == '':
            host = '127.0.0.1'

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))

        self.recv_buf = ''

        # Send cookie, little-endian coded
        self.send_raw(struct.pack('>l', cookie))

        # Recieve and print welcome message
        sys.stdout.write(self.recv())

    def send_raw(self, data):
        while data:
            n = self.socket.send(data)
            data = data[n:]

    def send(self, data):
        self.send_raw(struct.pack('>l', len(data)) + data)

    def recv(self):
        length = None
        while length is None or len(self.recv_buf) < length:
            d = self.socket.recv(1000)
            if not d:
                raise InspectError('connection closed by server')
            self.recv_buf = self.recv_buf + d

            if length is None:
                if len(self.recv_buf) < 4:
                    continue
                length = struct.unpack('>l', self.recv_buf[:4])[0]
                self.recv_buf = self.recv_buf[4:]

        d = self.recv_buf[:length]
        self.recv_buf = self.recv_buf[length:]

        return d

    def loop(self):
        try:
            while 1:
                expr = raw_input('>>> ')
                if expr:

                    # If first character of expr is a space,
                    # then this is a multiline statement.
                    # Read more lines until we get an empty one

                    if expr[0] == ' ':
                        lines = [expr[1:]]

                        while 1:
                            d = raw_input('... ')
                            lines.append(d[1:])
                            if not d:
                                break

                        expr = string.join(lines, '\n')

                    self.send(expr)
                    sys.stdout.write(self.recv())
        except EOFError:
            self.socket.close()


def main():
    d, name, db, argv = rdb.get_display_opts(rdb.stdopts)
    Inspect(d).loop()

if __name__ == '__main__':
    main()
