#####################
Real-time annotations
#####################

``realtime_annotate.py`` is a real-time annotation program for Unix
(and maybe Windows, but after replacing the curses module with an
alternative—patches are welcome).

The annotations handled by this program are entered in real-time with
a **single key** (with a meaning, e.g., "i" for "interesting
moment"), and an **optional digit** (that can be used for instance for
indicating a degree, e.g. "u9" could mean "extremely interesting").

Annotations have a **time stamp**. In a practical application, a piece
of music, etc. plays alongside the program, and they have synchronized
clocks (thanks to the command ``set_time``).

The program optionally automatically start and stop some player (music
player, etc.) when starting and stopping the annotation process. An
implementation for automatically starting and stopping MIDI
instruments is provided.

.. !!! update all uses of simple JSON => edit or automated
   analysis simple and perenial,

.. !!! YAML > JSON
   
Annotations are stored in a file that can be relatively easily edited
by hand if needed (a YAML file).


Installation
============

The program runs directly with Python 3.4 (and maybe earlier Python 3
versions).

The only required non-standard module is PyYAML_. If necessary, it can
be replaced in the code by a standard module like pickle or json (this
is almost a drop-in replacement: the main difference is that files
must be opened in binary mode, for pickle).

.. !!!!!! EITHER indicate how to install PyYAML, or move to JSON. I
   could convert annotations to [(H, M, S), key] and back (directly in
   the AnnotationList object). THEN I should document the structure of
   the output file, and indicate how to manipulate it in Python
   (AnnotationList)—or maybe later, when *I* do it. NOW, why would we
   need to read the file when we have AnnotationList objects that we
   can study? NOT CLEAR YET. pickle might actually be good. SETTLE THIS.
   

Configuration of the annotations
================================

.. !!!! Idea: include definition of annotations in the annotations
   file?? design (updates, modification [copy at creation,
   dump/replace for modification])?
   
The possible annotations are configured by the user in a simple text
file. The format is as follows::

.. !!!!!! refer to "help load_keys" command in the program.

**Important**:

.. !!! Include the following
   



.. !!!!  

Automatic play
==============

.. !!!!!!! Code plugin architecture for player, with MIDI as an
   example. User module, I guess, imported through a command-line
   option. I MUST handle the player help system as well. I MUST update
   the documentation below.
   
The program automatically plays music through MIDI instruments during
the real-time annotation phase, if configured appropriately (see the
messages printed by the program about MIDI).

The program can be extended to automatically play something else, if
needed (by modifying functions ``player_start()`` and
``player_stop()``).

Additional help
===============

The program launches a command-line interface that provides more help
(``?`` or ``help`` command).

Contact
=======

This program was written by `Eric O. LEBIGOT (EOL)
<mailto:eric.lebigot@normalesup.org>`_.

.. _PyYAML: http://pyyaml.org/wiki/PyYAML

