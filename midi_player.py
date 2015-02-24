"""
Plugin for realtime_annotate.py, for automatically starting and
stopping MIDI devices.

(c) 2015 by Eric O. LEBIGOT (EOL)
"""

__version__ = "0.9"
__author__ = "Eric O. LEBIGOT (EOL) <eric.lebigot@normalesup.org>"

import sys
import math

try:
    # simplecoremidi 0.3 almost works: it needs an undocumented
    # initial SysEx which is ignored, which is not clean.
    #
    # More generally, any module that can send MIDI messages would
    # work.
    import rtmidi
    
except ImportError:
    sys.exit("MIDI support not available."
             " It can be enabled with the python-rtmidi module.")
    
print("""\
MIDI synthetizer support enabled: make sure that your synthetizer listens
to MMC messages (in Logic Pro: menu File > Project Settings > Synchronization >
MIDI > Listen to MMC Input).""")


# This initialization code is from the documentation (it is required):
midiout = rtmidi.MidiOut()
if midiout.get_ports():
    midiout.open_port(0)
else:
    midiout.open_virtual_port("realtime_annotate.py")

def send_MMC_command(command):
    """
    Send a MIDI Machine Control command.

    Referene: http://en.wikipedia.org/wiki/MIDI_Machine_Control.

    command -- value of the command (e.g. play = 2, stop = 1, etc.)
    """
    midiout.send_message((0xf0, 0x7f, 0x7f, 0x06, command, 0xf7))

start = lambda: send_MMC_command(2)
stop = lambda: send_MMC_command(1)

def set_time(hours, minutes, seconds):
    """
    Set the MIDI players to the given time + 1 hour.

    hours and minutes are integers. seconds is a float.
    minutes and seconds are in [0; 60).

    hours must be in [0; 255].

    Sub-second time setting is approximate, and is handled by setting
    a frame number based on 25 frames/seconds.
    """

    # The seconds must be split into integer seconds and fractional seconds:
    integer_seconds, fractional_seconds = math.modf(seconds)
    
    midiout.send_message(bytearray.fromhex(
        "F0 7F 7F 06 44 06 01 {hours:2x} {minutes:2x} {seconds:2x} {frames:2x}"
        " {subframes} F7".format(
            hours=hours+1, minutes=minutes, seconds=integer_seconds,
            frames=int(round(25*fractional_seconds)))))
