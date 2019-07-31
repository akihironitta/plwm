#
# opacity.py -- set window opacity based on focus
#
#	Copyright (C) 2008  David H. Bronke <whitelynx@gmail.com>
#
#	This program is free software; you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation; either version 2 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program; if not, write to the Free Software
#	Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import wmanager, wmevents, cfilter
from Xlib import X, Xatom

# Client mixin
class TransparentClient:
	"""Client mixin. Sets opacity according to focus and client filters.

	Class members:
		opacity_(un)focused_default - sets the default opacity for (un)focused
			windows.
		opacity_(un)focused_clients - sets the opacity for specific windows,
			specified by client filters, depending on focus.
		opacity_ignore_clients - client filter which specifies clients to ignore.
			These clients will not have the _NET_WM_WINDOW_OPACITY property set.

	You can also set a client's opacity directly, using the opacity_set() method.
	"""

	opacity_focused_default = 1.0
	opacity_unfocused_default = 0.7

	opacity_focused_clients = ()
	opacity_unfocused_clients = ()

	opacity_ignore_clients = cfilter.false

	def __client_init__(self):
		self.opacity_focused = None
		self.opacity_unfocused = None

		self._NET_WM_WINDOW_OPACITY = self.wm.display.intern_atom(
			'_NET_WM_WINDOW_OPACITY'
		)

		if not self.opacity_ignore_clients(self):
			for filter, opacity in self.opacity_focused_clients:
				if filter(self):
					self.opacity_focused = opacity
					break
			else:
				self.opacity_focused = self.opacity_focused_default

			for filter, opacity in self.opacity_unfocused_clients:
				if filter(self):
					self.opacity_unfocused = opacity
					break
			else:
				self.opacity_unfocused = self.opacity_unfocused_default

			if self.focused:
				self.opacity_get_focus(None)
			else:
				self.opacity_lose_focus(None)

			# Set up dispatchers for the opacity changes
			self.dispatch.add_handler(
				wmevents.ClientFocusIn,
				self.opacity_get_focus
			)
			self.dispatch.add_handler(
				wmevents.ClientFocusOut,
				self.opacity_lose_focus
			)

	def opacity_get_focus(self, event):
		if self.opacity_focused is not None:
			self.opacity_set(self.opacity_focused)

	def opacity_lose_focus(self, event):
		if self.opacity_unfocused is not None:
			self.opacity_set(self.opacity_unfocused)

	def opacity_set(self, percent):
		opacity = int(percent * 0xFFFFFFFF)

		w = self.window
		while 1:
			r = w.query_tree()
			if r.parent == r.root:
				break
			w = r.parent

		w.change_property(
			self._NET_WM_WINDOW_OPACITY,
			Xatom.CARDINAL,
			32,
			[opacity],
			X.PropModeReplace
		)

		self.wm.display.sync()

