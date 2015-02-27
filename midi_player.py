"""
Plugin for realtime_annotate.py, for automatically starting and
stopping MIDI devices.

(c) 2015 by Eric O. LEBIGOT (EOL)
"""

__version__ = "1.0"
__author__ = "Eric O. LEBIGOT (EOL) <eric.lebigot@normalesup.org>"

# Reference for the MIDI Machine Control sequences:
# http://en.wikipedia.org/wiki/MIDI_Machine_Control.

import sys
import math

try:
    # simplecoremidi 0.3 almost works (it is OS X only, though): it
    # needs an undocumented initial SysEx which is ignored, which is
    # not clean.
    #
    # More generally, any module that can send MIDI messages would
    # work (rtmidi-python,...).
    import rtmidi  # This is from the python-rtmidi package
    
except ImportError:
    sys.exit("MIDI support not available."
             " It can be enabled with the python-rtmidi module.")
    
print("""\
*******************************************************************************
MIDI synthetizer support enabled: make sure that your synthetizer listens
to MMC messages (in Logic Pro: menu File > Project Settings > Synchronization >
MIDI > Listen to MMC Input).
*******************************************************************************
""")

# Play head setting is based on the following frame rate. It should
# ideally match the frame rate of the MIDI controllers. The user can
# change the FRAME_RATE value.
FRAME_RATE = 25  # frames/s

def out_port():
    """
    Return a MIDI port for output.
    """

    midi_out = rtmidi.MidiOut()

    # This initialization code is from the documentation (it is required):    
    if midi_out.get_ports():  # If there are available ports...
        midi_out.open_port(0)
    else:
        midi_out.open_virtual_port("realtime_annotate.py")

    return midi_out

midi_out = out_port()

def send_MMC_command(command):
    """
    Send a MIDI Machine Control command to all MIDI devices.

    command -- value of the command (e.g. play = 2, stop = 1, etc.),
    or bytes with the command.
    """
    if isinstance(command, int):
        command = bytes([command])
        
    midi_out.send_message(
        bytes([0xF0, 0x7F, 0x7F, 0x06])+command+bytes([0xF7]))

start = lambda: send_MMC_command(2)
stop = lambda: send_MMC_command(1)

def set_time(hours, minutes, seconds):
    """
    Set the MIDI players to the given time (note that by default Logic
    Pro X starts a MIDI recording at 1:00:00 [1 hour]).

    hours and minutes are integers. seconds is a float.
    minutes and seconds are in [0; 60).

    hours must be in [0; 255].

    Sub-second time setting is approximate, and is handled by setting
    a frame number based on FRAME_RATE frames/seconds. The player's
    frame rate should be set to a value close to this.
    """

    assert 0 <= hours <= 255, (
        "This number of hours cannot be handled: {}.".format(hours))
    
    # The seconds must be split into integer seconds and fractional seconds:
    fractional_seconds, seconds = math.modf(seconds)
    seconds = int(seconds)

    send_MMC_command(bytes([
        0x44, 0x06, 0x01,
        hours, minutes, seconds, int(FRAME_RATE*fractional_seconds), 0]))


