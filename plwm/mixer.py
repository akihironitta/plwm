#
# mw_mixer.py -- control and view volume
#
#    Copyright (C) 2002  Peter Liljenberg <petli@ctrl-c.liu.se>
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
import re
import os

from plwm import event, wmanager

# This is all a bit hacky.  Possibly something more cooked should be
# presented to the user than just affecting different device controls
# directly.  The interface adapters are not very well designed, and
# very sensitive to the output format of the various tools.

# Devices that can be used
MASTER = 'vol' # named thus for backward compitability
PCM = 'pcm'


MixerIOEventType = event.new_event_type()
MixerTimeoutEventType = event.new_event_type()

class ReximaInterface:
    dev_re = re.compile(r'^([a-z0-9]+)\s+(\d+)(, (\d+))?', re.MULTILINE)

    def probe_cmd(self):
        return 'type rexima > /dev/null 2>&1'

    def get_cmd(self):
        return 'rexima -v'

    def set_cmd(self, dev, val1, val2):
        if val2 is None:
            return 'rexima %s %d' % (dev, val1)
        else:
            return 'rexima %s %d,%d' % (dev, val1, val2)

    def parse_output(self, data):
        groups = self.dev_re.findall(data)
        devs = []

        for dev, ls1, skip, ls2 in groups:
            if not ls1:
                continue
            left = int(ls1)
            if not ls2:
                devs.append((dev, left))
            else:
                right = int(ls2)
                devs.append((dev, (left, right)))

        return devs


class AlsaInterface:
    TO_ALSA = { MASTER: 'Master',
                PCM: 'PCM',
                }

    FROM_ALSA = { 'Master': MASTER,
                  'PCM': PCM,
                  }

    GROUP_RE = re.compile(r'^Simple mixer control ',
                          re.MULTILINE)
    DEVICE_RE = re.compile(r"^'([^']+)',0")
    VOLUME_RE = re.compile(r'^  ([^:]+): Playback \d+ \[(\d+)%\]',
                           re.MULTILINE)

    def probe_cmd(self):
        return 'test -d /proc/asound && type amixer > /dev/null 2>&1'

    def get_cmd(self):
        return 'amixer'

    def set_cmd(self, dev, val1, val2):
        try:
            dev = self.TO_ALSA[dev]
        except KeyError:
            return None
            
        if val2 is None:
            return 'amixer set %s %d%% > /dev/null' % (dev, val1)
        else:
            return 'amixer set %s %d%%,%d%% > /dev/null' % (dev, val1, val2)

    def parse_output(self, data):
        groups = self.GROUP_RE.split(data)
        devs = []

        for g in groups:
            m = self.DEVICE_RE.search(g)
            if not m or not self.FROM_ALSA.has_key(m.group(1)):
                continue

            dev = self.FROM_ALSA[m.group(1)]

            mono = None
            left = None
            right = None

            for channel, volume in self.VOLUME_RE.findall(g):
                if channel == 'Mono':
                    mono = int(volume)
                elif channel == 'Front Left':
                    left = int(volume)
                elif channel == 'Front Right':
                    right = int(volume)

            wmanager.debug('mixer', 'dev %s: %s,%s or %s', dev, left, right, mono)

            if left is not None and right is not None:
                devs.append((dev, (left, right)))
            elif mono is not None:
                devs.append((dev, mono))

        return devs


INTERFACE_CLASSES = (ReximaInterface, AlsaInterface)

# wm mixin
class Mixer:
    def __wm_init__(self):
        for ifclass in INTERFACE_CLASSES:
            interface = ifclass()
            status = self.system(interface.probe_cmd(), fg = 1)

            # Probe OK?
            if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
                wmanager.debug('mixer', 'using interface %s', ifclass.__name__)
                self.mixer_interface = interface
                break
        else:
            wmanager.debug('mixer', 'could not find any interface to use')
            self.mixer_interface = None
            return

        self.dispatch.add_handler(MixerIOEventType, self.mixer_io_event)
        self.dispatch.add_handler(MixerTimeoutEventType,
                                  self.mixer_timout)

        self.mixer_devs = {}

        self.mixer_mute_devs = {}

        self.mixer_status_msg = None
        self.mixer_timer_event = None

        self.mixer_cmd_out = None
        self.mixer_update_settings()

    def mixer_update_settings(self):
        if self.mixer_interface is None:
            wmanager.debug('mixer', 'no mixer interface')
            return

        if self.mixer_cmd_out is not None:
            wmanager.debug('mixer',
                           'previous update command has not finished yet')
            return

        pipes = self.system(self.mixer_interface.get_cmd(), redirect = 1)

        self.mixer_cmd_out = pipes[1]
        self.mixer_cmd_data = ''
        self.mixer_cmd_event = event.FileEvent(MixerIOEventType,
                                               self.mixer_cmd_out,
                                               event.FileEvent.READ)
        self.events.add_file(self.mixer_cmd_event)


    def mixer_io_event(self, evt):
        d = self.mixer_cmd_out.read()
        if d:
            self.mixer_cmd_data = self.mixer_cmd_data + d
            return

        # command finished, update values
        self.mixer_cmd_event.cancel()
        self.mixer_cmd_event = None
        self.mixer_cmd_out.close()
        self.mixer_cmd_out = None

        devs = self.mixer_interface.parse_output(self.mixer_cmd_data)

        for dev, val in devs:
            self.mixer_devs[dev] = val


    def mixer_timout(self, evt):
        if self.mixer_status_msg is not None:
            self.mixer_status_msg.pop()
            self.mixer_status_msg = None
            self.mixer_timer_event = None


    def mixer_status_view(self, devs = None, stereo = 0, timeout = 5):
        if self.mixer_interface is None:
            wmanager.debug('mixer', 'no mixer interface')
            return

        if devs is None:
            devs = self.mixer_devs.keys()

        msg = ''
        for dev in devs:
            try:
                val = self.mixer_mute_devs[dev]
                valstr = 'MUTE:%s' % val
            except KeyError:
                try:
                    values = self.mixer_devs[dev]

                    if type(values) is types.TupleType:
                        if stereo:
                            valstr = '%s:%s' % values
                        else:
                            valstr = str(values[0])
                    else:
                        valstr = str(values)
                except KeyError:
                    valstr = 'N/A'

            msg = '%s  [%s %s]' % (msg, dev, valstr)

        if self.mixer_status_msg is None:
            self.mixer_status_msg = self.current_screen.modestatus_new(msg)
        else:
            self.mixer_status_msg.set(msg)

        if self.mixer_timer_event is not None:
            self.mixer_timer_event.cancel()

        self.mixer_timer_event = event.TimerEvent(MixerTimeoutEventType,
                                                  after = timeout)
        self.events.add_timer(self.mixer_timer_event)


    def mixer_get(self, dev, stereo = 0):
        if self.mixer_interface is None:
            wmanager.debug('mixer', 'no mixer interface')
            return None

        try:
            values = self.mixer_devs[dev]

            if type(values) is types.TupleType:
                return values[0]
            else:
                return values
        except KeyError:
            return None


    def mixer_set(self, dev, val1, val2 = None):
        if self.mixer_interface is None:
            wmanager.debug('mixer', 'no mixer interface')
            return

        try:
            values = self.mixer_devs[dev]
        except KeyError:
            return

        assert val1 >= 0 and val1 <= 100
        assert val2 is None or (val2 >= 0 and val2 <= 100)

        if type(values) is types.TupleType:
            if val2 is None:
                val2 = val1

            self.mixer_devs[dev] = (val1, val2)
            cmd = self.mixer_interface.set_cmd(dev, val1, val2)
        else:
            self.mixer_devs[dev] = val1
            cmd = self.mixer_interface.set_cmd(dev, val1, None)

        if cmd:
            self.system(cmd, fg = 1)

            try: del self.mixer_mute_devs[dev]
            except KeyError: pass


    def mixer_mute(self, dev):
        """Toggle muteness of DEV."""

        if self.mixer_interface is None:
            wmanager.debug('mixer', 'no mixer interface')
            return

        if self.mixer_mute_devs.has_key(dev):
            old = self.mixer_mute_devs[dev]
            self.mixer_set(dev, old)
        else:
            old = self.mixer_get(dev)
            self.mixer_set(dev, 0)
            self.mixer_mute_devs[dev] = old

