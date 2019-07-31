#
# Internal events generated by the window manager core.
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

import os

class AddClient:
    def __init__(self, client):
        self.type = AddClient
        self.client = client

class RemoveClient:
    def __init__(self, client):
        self.type = RemoveClient
        self.client = client

class QuitWindowManager:
    def __init__(self):
        self.type = QuitWindowManager

class CurrentClientChange:
    def __init__(self, screen, client):
        self.type = CurrentClientChange
        self.screen = screen
        self.client = client

class ClientFocusOut:
    def __init__(self, client):
        self.type = ClientFocusOut
        self.client = client

class ClientFocusIn:
    def __init__(self, client):
        self.type = ClientFocusIn
        self.client = client

class ClientIconified:
    def __init__(self, client):
        self.type = ClientIconified
        self.client = client

class ClientDeiconified:
    def __init__(self, client):
        self.type = ClientDeiconified
        self.client = client

class CommandEvent:
    def __init__(self, type):
        self.type = type
        self.status = None

    def termsig(self):
        if os.WIFSIGNALED(self.status):
            return os.WTERMSIG(self.status)
        else:
            return None

    def exitstatus(self):
        if os.WIFEXITED(self.status):
            return os.WEXITSTATUS(self.status)
        else:
            return None
