#####################
Real-time annotations
#####################

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

  s start (between pieces, before the beginning)
  e end (0 = could be an end if needed)
  i inspired (0 = somewhat, 2 = nicely)
  u uninspired (0 = a little, 2 = very much)
  g glitch (0 = small, 2 = major)

The first letter is a keyboard key (case sensitive). Typing this key
will insert the annotation described afterwards (free text).

**Important**:

.. !!! Include the following
   
# Mapping from keyboard keys to the corresponding enumeration name
# (which must be a valid Python attribute name), followed by a blank
# and help text. The keys cannot be changed, as they are represent
# annotations in files.
#
# WARNING: Entries can only be:
# - extended in their name and help text (previous meanings should not
# be altered), and
# - added, and not removed, because this would make previous
# annotation files illegible.
#
# WARNING: Some keys are reserved for the control of the real-time
# interface: space, delete, and digits, and cannot be present here.



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

