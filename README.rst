Real-time annotations
*********************

``realtime_annotate.py`` is a real-time annotation program.

The annotations handled by this program are entered in real-time with
a **single key** (with a meaning, e.g., "i" for "interesting
moment"), and an **optional digit** (that can be used for instance for
indicating a degree, e.g. "u9" could mean "extremely interesting").

Annotations have a **time stamp**. In a practical application, a piece
of music, etc. plays alongside the program, and they have synchronized
clocks (thanks to the command ``set_time``).

Annotations are stored in a file that can be relatively easily edited
by hand if needed (a YAML file).

Installation
------------

The program runs with Python 3.

The only required non-standard module is PyYAML_.

If necessary, it can be replaced in the code by the standard module
``pickle``.

Configuration of the annotations
--------------------------------

The possible annotations are configured by the user in a simple text
file. The format is as follows::

.. !!!!!!!!! define and implement: "u uninteresting (0 = …)"

Automatic play
--------------

.. !!!!!!! Code plugin architecture for player, with MIDI as an
   example. User module, I guess, imported through a command-line
   option. I MUST handle the player help system as well.
   
The program automatically plays music through MIDI instruments during
the real-time annotation phase, if configured appropriately (see the
messages printed by the program about MIDI).

The program can be extended to automatically play something else, if
needed (by modifying functions ``player_start()`` and
``player_stop()``).

Additional help
---------------

The program launches a command-line interface that provides more help
(``?`` or ``help`` command).

.. _PyYAML: http://pyyaml.org/wiki/PyYAML
