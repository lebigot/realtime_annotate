#####################
Real-time annotations
#####################

Overview
========

.. Benefits and description of the program for users, in one sentence:
   
``realtime_annotate.py`` is a light-weight program that **lets users
focus** on listening to a piece of music, watching a video, etc., and
**make pre-defined annotations** very efficiently,

.. How are the benefits obtained?
   
Users can focus on the annotation task thanks to having them enter
annotation with a **single keyboard key**, and to letting the program
**automatically handle time-related tasks** (time stamping, and
automatic scrolling of existing annotations):

.. _screenshot:

.. image:: doc/annotate.png

.. Some details connected to the introductory paragraph:
   
The **annotations** handled by this program are entered in real time
with a *single key* (with a meaning, e.g., "i" for "interesting
moment"), and an *optional digit* (that can be used for instance for
indicating a degree, e.g. "i9" could mean "extremely
interesting"). Their meaning is pre-defined by the user before
starting the `annotation process`_.

Annotations have a **time stamp**, which is *automatically added* by
the program. In a practical application, a piece of music, etc. plays
alongside the program. The annotation timer of the program can be set
to the time of the event being annotated (command ``set_time``). For
example, the play head of a music player can thus be synchronized with
the user's annotation time stamps.

When going through an existing annotated event, existing **annotations
scroll on screen**. An upcoming annotation is *highlighted for one
second* before is scrolls down to the list of previous annotations:
the user does not have to check the timer in order to see whether he
has already entered some annotation). The user is thus freed from
managing time and time stamps. There should be no more inner
monologues like this one:

- *Did I already indicate that the melody is good, here?*
- *Let me check the timer…*
- *00:01:23…*
- *Let's see if there is already an annotation around that time…*
- *Yeah, there is one at 00:01:24, I have already handled this.*

All of this is automatically handled by the program through the
scrolling display of annotations around the current timer, and the
user can better focus on the quality of his real-time annotations.

Annotations for *multiple events* are stored in a single **JSON file**
with a simple format.  This format has the advantage of being
perennial. The collected annotations can also be conveniently
*manipulated by external programs* (for manual editing, automatic
analysis, etc.).

.. The optional feature is left at the end, as it is less immediately
   important:

The program optionally **automatically synchronizes** the annotation
timer with an **external player** (music player, etc.).  Thus, it can
automatically start and stop the player when starting and stopping the
`annotation process`_, and can set the player's play head when the
annotation timer is set to a specific time.  *MIDI instruments* can be
automatically controlled with the `provided MIDI controller
<midi_player.py>`_. Users can control *other kinds of players* by
writing a few Python functions.

.. Concrete implementation details and features:
   
The program runs in text mode, in a terminal:

.. image:: doc/shell.png

The command shell of ``realtime_annotate.py`` provides the **automatic
completion** of commands and arguments, through the tabulation key.

Platforms and installation
==========================

The program runs directly with Python 3.4+. It currently runs on Unix
(including OS X).

Downloading `realtime_annotate.py <realtime_annotate.py>`_ is
sufficient for installing this program. It only uses standard modules
(of Python 3.4+)—they are generally installed along with Python.

Two example configuration files are provided:

- a key assignment configuration: `music_annotations.txt
  <music_annotations.txt>`_,

- an optional player controller, for synchronizing MIDI players with
  the annotation timer: `midi_player.py <midi_player.py>`_.


Usage
=====

The program is simply run with ``python3.4 realtime_annotate.py
<annotation_file>``, where ``python3.4`` should be replaced by the
name of the local Python 3.4+ interpreter, and where
``<annotation_file>`` is the path to the JSON file used for saving and
reading annotations.

Users can then control the annotation process by using a command
shell. The main command is ``annotate``: it starts the real-time
`annotation process`_ proper.

Help
====

.. The help section comes relatively early because it helps users to
   quickly test the program by themselves:

Help can be obtained with the ``-h`` or ``--help`` option of
``realtime_annotate.py``.

Help on the commands of the ``realtime_annotate.py`` command shell is
available through ``?`` or ``help``.

Workflow
========

New annotation file
-------------------

When a new annotation file is created, a **list of annotation keys**
must first be attached to it: this defines the *meaning of the keys*
used for entering annotations (``load_keys`` command).

The possible annotations and annotation keys are configured by the
user in a simple text file. For more information on the format of this
file, see the built-in help: ``help load_keys``. An simple `example
<music_annotations.txt>`_ for annotating music recordings is provided.

Typical workflow
----------------

A typical workflow starts by simply selecting an **event** to be
annotated (command ``select_event``). A *new event* can be created by
simply giving a new event name. *Existing events* are listed with
``list_events``.

Selecting an event to be annotated *automatically sets the annotation
timer* (to the annotation before the last time reached). If needed, a
different annotation **starting time** can be set with the
``set_time`` command. If a music player, etc. is controlled by the
program, its play head is set automatically to the same time.

The selected event can then be annotated in real time with the
``annotate`` command.

.. _annotation process:

Annotation process
""""""""""""""""""

The ``annotate`` command launches the real-time annotation process
(see the screenshot_ in the overview).

The **annotation timer** starts running when the user enters the
command. The starting annotation timer is typically set (beforehand)
so that it coincides with the event's time when the ``annotate``
command is entered (i.e. when the Enter key is pressed): this way, the
annotation timer is the same as the event's timer (play head location
of a music player, etc.), which is convenient. If a music controller
is used (see below_), this time synchronization can be automatic.

Existing **annotations automatically scroll** on the
screen.

All **actions** are run with a *single* keyboard key (listed in the
help at the bottom of the ``annotate`` screen):

- Typing the **key** of one of the user-defined annotations adds it with
  the current annotation timer as a time stamp.
  
- Any typed **digit** adds a **value** to (or changes the value of)
  the *last* annotation (for example, the glitch at 00:00:12.6 in the
  screenshot above has value 0).

- Existing annotations can also be **deleted**: the last annotation
  (from the list of previous annotations) is deleted with the delete
  key.

- **Stopping** the annotation process is done with the space key. If a
  player controller is used (``--player`` option), the player
  is stopped.

Annotation file format
======================

The annotation file `JSON <http://en.wikipedia.org/wiki/Json>`_
structure should be mostly self-explanatory.

Annotation times are stored as ``[hours, minutes, seconds]``.
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

.. _below:

Synchronization with an external player
=======================================

The program can optionally automatically synchronize an external
player (music player, etc.) with the annotation timer. This is done
through writing a Python module that contains a few player control
function, and specifying it through the ``--player`` option
(e.g. ``--player midi_player``).  A working `MIDI instrument
controller <midi_player.py>`_ is provided; it can be used as an
example.  See ``realtime_annotate.py -h`` for details on how to write
a player controller module.

License
=======

This program and its documentation are released under the `Revised BSD
License <LICENSE.txt>`_.

Patches
=======

Patches for supporting earlier Python versions or for Windows are
welcome. Support for earlier versions of Python would require a
replacement of the ``enum`` standard module. Windows support would
require replacing the curses module with an alternative.

Contact
=======

This program was written by `Eric O. LEBIGOT (EOL)
<mailto:eric.lebigot@normalesup.org>`_. Patches, donations, bug
reports and feature requests are welcome.

