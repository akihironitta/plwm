#
# inspect.py -- Allow inspection of PLWM internals
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

import wmanager, event, modewindow, wmevents
import socket
import sys
import traceback
import struct
import random
import cStringIO

InspectFileEventType = event.new_event_type()

# wm mixin
class InspectServer:
    inspect_enabled_at_start = 0

    def __wm_init__(self):
        self.inspect_socket = None
        self.inspect_cookie = None
        self.inspect_socket_event = None
        self.inspect_clients = None
        self.inspect_message = None

        self.PLWM_INSPECT_SERVER = self.display.intern_atom('_PLWM_INSPECT_SERVER')

        self.dispatch.add_handler(InspectFileEventType,
                                  self.inspect_handle_file_event)

        self.dispatch.add_handler(wmevents.QuitWindowManager,
                                  self.inspect_quitwm_handler)

        if self.inspect_enabled_at_start:
            self.inspect_enable()

    def inspect_quitwm_handler(self, evt):
        self.inspect_disable(force = 1)

    def inspect_enable(self):
        # Inspection already enabled
        if self.inspect_socket is not None:
            return

        wmanager.debug('inspect', 'enabling inspect server')

        # Listen on any port on the local interfaces
        self.inspect_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.inspect_socket.bind(('', 0))
        self.inspect_socket.listen(5)

        self.inspect_socket_event = event.FileEvent(InspectFileEventType,
                                                    self.inspect_socket,
                                                    event.FileEvent.READ)

        self.events.add_file(self.inspect_socket_event)

        # Create a authentication cookie, and store it and the
        # portnumber in a property on screen 0

        addr, port = self.inspect_socket.getsockname()
        self.inspect_cookie = random.randint(0, 0x7ffffffe)

        self.default_screen.root.change_property(self.PLWM_INSPECT_SERVER,
                                             self.PLWM_INSPECT_SERVER,
                                             32, [port, self.inspect_cookie])

        self.inspect_clients = {}

        self.inspect_message = modewindow.Message(.2, modewindow.LEFT, 0, '[Inspect]')
        for s in self.screens:
            try:
                s.modewindow_add_message(self.inspect_message)
            except AttributeError:
                pass

    def inspect_disable(self, force = 0):
        # Inspect already disabled
        if self.inspect_socket is None:
            return

        if self.inspect_clients:

            # Shut down all clients
            if force:
                for c in self.inspect_clients.values():
                    c.close()

            # Beep and abort
            else:
                self.display.bell(50)
                return

        wmanager.debug('inspect', 'disabling inspect server')

        for s in self.screens:
            try:
                s.modewindow_remove_message(self.inspect_message)
            except AttributeError:
                pass

        self.inspect_message = None
        self.inspect_clients = None
        self.default_screen.root.delete_property(self.PLWM_INSPECT_SERVER)
        self.inspect_cookie = None
        self.inspect_socket_event.cancel()
        self.inspect_socket_event = None
        self.inspect_socket.close()
        self.inspect_socket = None

    def inspect_toggle(self, force = 0):
        if self.inspect_socket is None:
            self.inspect_enable()
        else:
            self.inspect_disable(force)


    def inspect_handle_file_event(self, evt):
        if self.inspect_socket is None:
            return

        if evt is self.inspect_socket_event:
            self.inspect_create_new_client()

        else:
            try:
                c = self.inspect_clients[evt]
            except KeyError:
                pass
            else:
                c.handle_file_event(evt)

    def inspect_create_new_client(self):
        conn, addr = self.inspect_socket.accept()

        wmanager.debug('inspect', 'connection from %s', addr)

        client = InspectClient(self, conn, addr)
        self.inspect_clients[client.event] = client
        self.inspect_set_message()

    def inspect_set_message(self):
        if len(self.inspect_clients) == 0:
            self.inspect_message.set_text('[Inspect]')
        elif len(self.inspect_clients) == 1:
            self.inspect_message.set_text('[Inspect: 1 client]')
        else:
            self.inspect_message.set_text('[Inspect: %d clients]' % len(self.inspect_clients))

    def inspect_client_closed(self, client):
        try:
            del self.inspect_clients[client.event]
        except KeyError:
            pass
        self.inspect_set_message()

class InspectClient:
    def __init__(self, wm, sock, addr):
        self.wm = wm
        self.socket = sock
        self.addr = addr
        self.authed = 0

        self.event = event.FileEvent(InspectFileEventType, self.socket,
                                     event.FileEvent.READ)
        self.wm.events.add_file(self.event)

        self.recv_len = 0
        self.recv_buf = ''
        self.send_buf = ''

        self.globals = __builtins__.copy()
        self.globals['wm'] = self.wm

    def handle_file_event(self, evt):
        if evt.state & event.FileEvent.READ:
            try:
                d = self.socket.recv(500)
            except socket.error, err:
                wmanager.debug('inspect', 'client %s closed on failed recv: %s',
                               self.addr, err)
                self.close()
                return

            if not d:
                wmanager.debug('inspect', 'client %s closed', self.addr)
                self.close()
                return

            self.recv_buf = self.recv_buf + d

            # First four bytes sent must the the authentication cookie
            if not self.authed:
                if len(self.recv_buf) >= 4:
                    cookie = struct.unpack('>l', self.recv_buf[:4])[0]
                    self.recv_buf = self.recv_buf[4:]

                    if cookie == self.wm.inspect_cookie:
                        self.authed = 1
                        self.output('Welcome to PLWM at %s\n'
                                    % self.wm.display.get_display_name())
                    else:
                        wmanager.debug('inspect',
                                       'client %s closed on wrong cookie: %d',
                                       self.addr, cookie)
                        self.close()
                        return

            while 1:
                # No length recieved yet, parse a little-endian fourbyte length
                if self.recv_len == 0:
                    if len(self.recv_buf) >= 4:
                        self.recv_len = struct.unpack('>l', self.recv_buf[:4])[0]

                        # Do sanity check on length, abort connection if it is < 0
                        if self.recv_len < 0:
                            wmanager.debug('inspect',
                                           'client %s closed, sent negative length: %d',
                                           self.addr, self.recv_len)
                            self.close()
                            return

                        self.recv_buf = self.recv_buf[4:]
                    else:
                        break

                # All data of expression read, execute it
                if self.recv_len <= len(self.recv_buf):
                    data = self.recv_buf[:self.recv_len]
                    self.recv_buf = self.recv_buf[self.recv_len:]
                    self.recv_len = 0

                    self.exec_data(data)
                else:
                    break

        if evt.state & event.FileEvent.WRITE:
            # Send any unsent data
            try:
                n = self.socket.send(self.send_buf)
            except socket.error, err:
                wmanager.debug('inspect', 'client %s closed on failed send: %s',
                               self.addr, err)
                self.close()
                return

            self.send_buf = self.send_buf[n:]

            # If there are no data left to send, clear the
            # WRITE flag in the event to avoid a lot of
            # select follies.

            if len(self.send_buf) == 0:
                evt.set_mode(clear = event.FileEvent.WRITE)


    def exec_data(self, data):

        # We replace the standard files with temporary ones.  stdin is
        # redirected from /dev/null, and stdout and stderr is sent to
        # a StringIO object.

        old_stdin = sys.stdin
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        f = cStringIO.StringIO()
        try:
            sys.stdin = open('/dev/null', 'r')
            sys.stdout = sys.stderr = f

            # Compile and execute the expressions.  print statements
            # and expression values will be sent to the StringIO
            # object, as will any exception traceback

            try:
                c = compile(data, '<string>', 'single')
                exec c in self.globals
            except:
                traceback.print_exc(None, f)

        finally:
            # Restore the standard files
            sys.stdin = old_stdin
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        self.output(f.getvalue())

    def output(self, data):
        # Encode output for sending, and tell the event loop that
        # we are interested in WRITE readiness

        self.send_buf = self.send_buf + struct.pack('>l', len(data)) + data
        self.event.set_mode(set = event.FileEvent.WRITE)

    def close(self):
        self.socket.close()
        self.event.cancel()
        if self.wm:
            self.wm.inspect_client_closed(self)
            self.wm = None
            self.globals = None
