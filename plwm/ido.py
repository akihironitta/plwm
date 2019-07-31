#
# ido.py -- interactively choose a client to do something with
#
#    Copyright (C) 2009  Peter Liljenberg <peter.liljenberg@gmail.com>
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

"""Interactivly select a client to do something with it.  This is
basically a plwm implementation of ido.el in Emacs.

Create an IdoWindow for a given screen, and call its select() method
to select one of the clients passed in.

A window pops up with a prompt line (not indicated by with any cursor,
though) and a list of titles and window classes for all clients
provided.

By entering text the list of clients is reduced to only the ones whose
title or class contains that text.  The matching is case insensitive.

If the entered text continues in the same way for several of the
clients, this is indicated within brackets after the prompt.  Hit tab
to expand the common text.

The last character can be deleted with backspace, and the last word
with M-backspace.

Cycle the list of matching windows forward and backward with C-s and
C-r.

Choose the window at the top of the list with Return.  A provided
callback will be called with the selected client object and can then
do whatever action is suitable on it.

Cancel the selection with C-g or Escape.  The callback is called with
None in this case.
"""

from Xlib import X

import keys
import message
import wmanager


class IdoWindow(object):

    """Interactive selection window.

    The object is bound to a given screen, and can be reused by
    subsequent calls to select().
    """

    window_font = "fixed"
    window_foreground = "black"
    window_background = "white"
    window_bordercolor = "black"
    window_borderwidth = 3
    window_draw = X.GXset

    prompt = 'Window: '
    
    def __init__(self, screen):
        self.screen = screen
        self.wm = screen.wm
        self.message = message.Message(
            screen,
            self.window_font,
            self.window_draw,
            self.window_foreground,
            self.window_background,
            self.window_bordercolor,
            self.window_borderwidth,
            0) # no timeouts

        self.clients = None

    def select(self, clients, callback):
        """Let user select one of the CLIENTS, and when selected call
        CALLBACK with the selected client object, or None if the
        selection was aborted.

        Will take over keyboard focus, and assumes that not much else
        goes on while the selection window is open.
        """
        
        self.clients = list(clients) # copy, since we will modify it
        self.callback = callback

        self.match = ''
        self.common_prefix = None
        
        lines = ['%s [%s]' % (c.get_title(), c.res_class) for c in clients]

        # Add the prompt
        lines.insert(0, self.prompt)

        # Init the window, and remember its max geometry
        self.width, self.height = self.message.setup(lines, align = 'left')

        self.x = self.screen.root_x + max(
            0, (self.screen.root_width - self.width) / 2)

        self.y = self.screen.root_y + max(
            0, (self.screen.root_height - self.height) / 2)

        # Take a copy of the original lists
        self.all_clients = list(self.clients)
        self.all_lines = list(self.message.lines)
        
        # store the prompt by itself
        self.prompt_line = self.all_lines[0]
        del self.all_lines[0]

        # Show window and start interactivity
        self.message.display(self.x, self.y)
        IdoKeyHandler(self)

    #
    # Internal event handling methods below
    #

    def update(self):
        # Figure out what the current selection is and redraw
        # everything.  This could be smarter by taking previous
        # selection(s) into account, but CPU is cheap these days.

        self.clients = []
        lines = []
        prefixes = []

        # Find all matching clients
        
        for i, client in enumerate(self.all_clients):
            # Search in title first
            title = client.get_title().lower()
            p = title.find(self.match)
            if p != -1:
                self.clients.append(client)
                lines.append(self.all_lines[i])
                prefixes.append(title[p + len(self.match):])
                continue

            # And then in resource class
            res_class = client.res_class.lower()
            p = res_class.find(self.match)
            if p != -1:
                self.clients.append(client)
                lines.append(self.all_lines[i])
                prefixes.append(res_class[p + len(self.match):])

        # See if they have some common prefix
        self.common_prefix = ''
        if len(prefixes) > 1:
            for i in range(min([len(p) for p in prefixes])):
                c = prefixes[0][i]

                for p in prefixes:
                    if p[i] != c:
                        c = None
                        break

                if c is None:
                    break

                self.common_prefix += c

        # Rebuild prompt
        prompt = self.prompt + self.match
        
        if self.common_prefix:
            prompt += '[' + self.common_prefix + ']'

        if not self.clients:
            prompt += ' (no match)'

        # Play fast'n'loose with the internal state of Message
        self.prompt_line.name = prompt
        self.message.lines = [self.prompt_line]
        self.message.lines.extend(lines)

        self.message.redraw()


    def finish(self, selected):
        self.message.hide()

        if selected and len(self.clients):
            client = self.clients[0]
        else:
            client = None
            
        callback = self.callback

        # Drop references to working objects
        self.clients = None
        self.callback = None
        self.all_clients = None
        self.all_lines = None
        self.prompt_line = None
        
        # Finally tell our caller about it
        callback(client)

        
    def do_select(self):
        if self.clients:
            self.finish(1)
            return 1
        else:
            return 0

    def do_cancel(self):
        self.finish(0)
        

    def do_tab(self):
        if self.common_prefix:
            self.match += self.common_prefix
            self.common_prefix = None
            self.update()


    def do_add_char(self, evt):
        if evt.type != X.KeyPress: return
        sym = self.wm.display.keycode_to_keysym(
            evt.detail, evt.state & X.ShiftMask != 0)
        chr = self.wm.display.lookup_string(sym)
        if chr:
            self.match += chr.lower()
            self.update()


    def do_delete_char(self):
        if self.match:
            self.match = self.match[:-1]
            self.update()

    
    def do_delete_word(self):
        if self.match:
            p = self.match.rfind(' ')
            if p != -1:
                self.match = self.match[:p]
            else:
                self.match = ''
            self.update()


    def do_cycle_forward(self):
        # Move the first displayed client/line last
        if len(self.clients) > 1:
            client = self.clients[0]
            i = self.all_clients.index(client)

            del self.all_clients[i]
            self.all_clients.append(client)

            line = self.all_lines[i]
            del self.all_lines[i]
            self.all_lines.append(line)

            self.update()

    def do_cycle_backward(self):
        # Move the last displayed client/line last
        if len(self.clients) > 1:
            client = self.clients[-1]
            i = self.all_clients.index(client)

            del self.all_clients[i]
            self.all_clients.insert(0, client)

            line = self.all_lines[i]
            del self.all_lines[i]
            self.all_lines.insert(0, line)

            self.update()
    

class IdoKeyHandler(keys.KeyGrabKeyboard):
    """Key handler in ido mode, replicating the Emacs interface.
    """

    timeout = None

    def __init__(self, window):
        keys.KeyGrabKeyboard.__init__(self, window.wm, X.CurrentTime)
        self.window = window
    
    def Return(self, evt):
        if self.window.do_select():
            self._cleanup()

    def C_g(self, evt):
        self.window.do_cancel()
        self._cleanup()

    Any_Escape = C_g

    def Tab(self, evt):
        self.window.do_tab()

    def BackSpace(self, evt):
        self.window.do_delete_char()

    def M_BackSpace(self, evt):
        self.window.do_delete_word()
        
    def C_s(self, evt):
        self.window.do_cycle_forward()

    def C_r(self, evt):
        self.window.do_cycle_backward()

    def _char(self, evt):
        self.window.do_add_char(evt)
        
keys.allmap(IdoKeyHandler, IdoKeyHandler._char)    
