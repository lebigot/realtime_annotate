#####################
Real-time annotations
#####################

``realtime_annotate.py`` is a light-weight real-time annotation
program. It runs in text mode.

The annotations handled by this program are entered in real time with
a **single key** (with a meaning, e.g., "i" for "interesting
moment"), and an **optional digit** (that can be used for instance for
indicating a degree, e.g. "i9" could mean "extremely interesting").

Annotations have a **time stamp**. In a practical application, a piece
of music, etc. plays alongside the program. The annotation timer of
the program can be set to the time of the event being annotated
(command ``set_time``), for instance so that the play head of a music
player is synchronized with the program's annotation timer.

The program optionally **synchronizes the annotation timer with an
external player** (music player, etc.).  Thus, it can automatically
start and stop the player when starting and stopping the annotation
process, and can set the player's play head when the annotation timer
is set to a specific time.  An `implementation <midi_player>`_ for
automatically starting and stopping MIDI instruments is provided
(option ``--player midi_player``).

Annotations are stored for multiple events in a single **JSON file**.
This format has the advantage of being perennial. The collected
annotations can also be conveniently manipulated by external programs
(for manual editing, automatic analysis, etc.).

Screenshots
===========

.. !!!!!
   
Installation and platforms
==========================

The program runs directly with Python 3.4+. Patches for support for
earlier Python versions are welcome.

It runs on Unix (including OS X). Windows support would require
replacing the curses module with an alternative: patches are welcome.

Usage
=====

The program is simply run with ``python3.4 realtime_annotate.py
<annotation_file>``, where ``python3.4`` should be replaced by the
name of the local Python 3.4+ interpreter, and where
``<annotation_file>`` is the path to the JSON file where annotations
will be saved and read.
   
Configuration of the annotations
================================

The possible annotations and annotation keys are configured by the
user in a simple text file. For more information, see the built-in
help for the ``load_keys`` command. An simple `example
<music_annotations.txt>`_ for annotating music recordings is provided.

Automatic play
==============

The program can optionally automatically synchronize some player
(music player, etc.) with the annotation timer. This is done through
writing a Python module that contains a few player control function,
and specifying it through the ``--player`` option (e.g. ``--player
midi_player``). See ``realtime_annotate.py -h`` for details.

Annotation file format
======================

The annotation file structure in JSON should be mostly self-explanatory.

Annotation times are stored as an ``[hours, minutes, seconds]`` array.
``hours`` and ``minutes`` are integers, and ``seconds`` is a
float. ``minutes`` and ``seconds`` are in the [0; 60) interval.  There
is no limit on the number of hours.

Annotations are stored as an array. This array contains the annotation
key (e.g. "i" for "interesting moment"). If the annotation has an
attached numerical value (number in 0–9), then the array contains a
second element with this value.

The JSON file also contains an object with the annotation keys and
their meaning. This part of the file can be conveniently updated by
``realtime_annotate.py`` through its ``load_keys`` command.

Additional help
===============

Help
====

Help can be obtained with the ``-h`` or ``--help`` option of
``realtime_annotate.py``.

The program launches a command shell. Help with the commands of this
shell is available through ``?`` or ``help``.

Contact
=======

This program was written by `Eric O. LEBIGOT (EOL)
<mailto:eric.lebigot@normalesup.org>`_. Patches, donations, bug
reports and feature requests are welcome.

