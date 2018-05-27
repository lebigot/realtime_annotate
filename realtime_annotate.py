#!/usr/bin/env python3

# Some comments are prefixed by a number of "!" marks: they indicate
# some notable comments (more exclamation marks indicate more
# important comments).

"""
Real-time annotation tool.

Annotations are timestamped. They contain user-defined values.

Optionally, some real-time player (music player, video player, MIDI
player,...) can be controlled so that annotation timestamps are
synchronized with the player (the player time head is automatically
set to the annotation timestamp; the player is started and stopped at
the same times as the annotation process).

(c) 2015–2018 by Eric O. LEBIGOT (EOL)
"""

__version__ = "1.5"
__author__ = "Eric O. LEBIGOT (EOL) <eric.lebigot@normalesup.org>"

# !! The optional player driven by this program must be defined by
# functions in a module stored in a variable named player_module. See
# the main program for two examples.

import collections
import pathlib
import cmd
import datetime
import shutil
import atexit
import curses  # For Windows, maybe UniCurses would work
import time
import sched
import bisect
import sys
import glob
import json
import re
import tempfile
import subprocess
import os

if sys.version_info < (3, 4):
    sys.exit("This program requires Python 3.4+, sorry.")

try:
    import readline  # Optional
except ImportError:  # Standard modules do not have to be all installed
    pass
else:
    # There is no need to complete on "-", for instance (the shell is
    # not a programming shell):
    readline.set_completer_delims(" ")

## Definition of a file locking function lock_file():

class FileLocked(OSError):
    """
    Raised when a file is locked.
    """

# Testing for os.name is less robust than testing for the modules
# that are needed:

# The file must be kept open for the lock to remain active.  Since we
# keep the lock for the duration of this program, there is no need to
# keep track of the file in order to unlock it later (the lock is
# released when the file closes, which happens automatically when this
# program exits):
lock_file_doc = """
    Cooperatively lock the file at the given path.
    
    Returns a value that must be kept in memory so that the lock not be
    released.

    Raises a FileLocked exception if the lock cannot
    be obtained."""
try:
    import fcntl
    def lock_file(file_path):
        locked_file = open(file_path, "r+")
        try:
            fcntl.flock(locked_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, PermissionError):
            raise FileLocked
        return locked_file
    lock_file.__doc__ = lock_file_doc
except ImportError:
    try:
        # !!!! This part of the code is for Windows and is therefore currently
        # irrelevant, because the curses library is required, which doesn't
        # work on Windows. However, it is left here as a reference in case
        # of a future Windows version.
        import msvcrt
        def lock_file(file_path):
            # !!! WARNING: this function is yet untested
            locked_file = open(file_path, "r+")
            try:
                msvcrt.locking(locked_file.fileno, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise FileLocked
            return locked_file
        lock_file.__doc__ = lock_file_doc
    except ImportError:
        # No file locking available:
        lock_file = lambda file_path: None

# Time interval between keyboard keys that are considered repeated:
REPEAT_KEY_TIME = datetime.timedelta(seconds=1)
# Time step when moving backward and forward in time during the
# annotation process:
NAVIG_STEP = datetime.timedelta(seconds=2)

class Time(datetime.timedelta):
    # ! A datetime.timedelta is used instead of a datetime.time
    # because the internal scheduler of this program must be added to
    # the current annotation timestamp so as to update it. This cannot
    # be done with datetime.time objects (which cannot be added to a
    # timedelta).
    """
    Timestamp compatible with a datetime.timedelta.
    """

    def to_HMS(self):
        """
        Returns the time as a tuple (hours, minutes, seconds), with
        seconds and minutes between 0 and 60 (not included). The
        number of hours has no limit.

        Hours and minutes are integers.

        Not tested with a negative duration.

        This can be inverted with Time(hours=..., minutes=..., seconds=...).
        """
        total_seconds = self.days*24*3600+self.seconds+self.microseconds/1e6
        (hours, minutes) = divmod(total_seconds, 3600)
        (minutes, seconds) = divmod(minutes, 60)
        return (int(hours), int(minutes), seconds)

    # Factory function:
    @classmethod
    def from_HMS(cls, HMS):
        """
        Return an instance from a simple (hour, minute, seconds) sequence.

        HMS -- (hour, minutes, seconds) sequence.
        """
        return cls(**dict(zip(("hours", "minutes", "seconds"), HMS)))

    def __str__(self):
        """
        ...HH:MM:SS.d format.
        """
        return "{:02}:{:02}:{:04.1f}".format(*self.to_HMS())

    def __sub__(self, other):
        """
        Subtraction.

        Returns a Time object.

        other -- datetime.timedelta.
        """
        return self + (-other)

    def __add__(self, other):
        """
        other -- object that can be added to a datetime.timedelta.
        """
        # ! A datetime.timedelta apparently does not return an element
        # of the type of self, so this is done manually here:
        new_time = other+self  # The order is important!
        # ! The class of the object cannot be changed, because it is a
        # built-in type:
        return Time(new_time.days, new_time.seconds, new_time.microseconds)


class TimestampedAnnotation:
    """
    Annotation made at a specific time.

    Main attributes:
    - time (datetime.timedelta)
    - annotation ([key, index_in_history] pair)

    A value can be added to the annotation. It is stored in the
    optional 'value' attribute. This is typically used for indicating
    an intensity (such as a small glitch, or a very uninspired
    part). A merit of this approach is that there is no restriction on
    the contents of value (which can be None, etc.). Another merit is
    that only annotations that have a value store one (in memory, on
    disk, etc.).
    """
    def __init__(self, timestamp, annotation):
        """
        timestamp -- timestamp for the annotation, as a datetime.timedelta.

        annotation -- annotation to be stored, as a [key,
        index_in_history] pair.
        """
        self.time = timestamp
        self.annotation = annotation

    def set_value(self, value):
        # !! This method exists mostly as a way of showing through
        # code that the value attribute can be set (it is optional,
        # and not set in __init__()).
        """
        Set the annotation's value.
        """
        self.value = value

    def __str__(self):

        result = "{} {}".format(self.time, self.annotation)

        if hasattr(self, "value"):
            result += " [value {}]".format(self.value)

        return result

    def to_builtins_fmt(self):
        """
        Return a version of the annotation with only Python builtin types
        (with no module dependency).

        This is useful for serializing the annotation (e.g. for JSON).

        Returns (time, annot), where time is an (hours, minutes, seconds)
        sequence, and where annot is [annotation] or [annotation, value], if a
        value is defined for the TimestampedAnnotation.
        """

        annotation = [self.annotation]
        if hasattr(self, "value"):
            annotation.append(self.value)

        return [self.time.to_HMS(), annotation]

    @classmethod
    def from_builtins_fmt(cls, timed_annotation):
        """
        Reverse of to_builtins_fmt().

        timed_annotation -- version of the annotation, as returned for
        instance by to_builtins_fmt().
        """

        annot = timed_annotation[1]  # [ [key, index], optional_value ]

        result = cls(Time.from_HMS(timed_annotation[0]), annot[0])

        if len(annot) > 1:  # Optional value associated with annotation
            result.set_value(annot[1])

        return result

class NoAnnotation(Exception):
    """
    Raised when a requested annotation cannot be found.
    """

class TerminalNotHighEnough(Exception):
    """
    Raised when the terminal is not high enough for a proper display.
    """

class EventData:
    """
    Data associated to an event.

    The event data is:
    - list of annotations (for a single reference) sorted by timestamp,
    - a live insertion cursor between annotations,
    - text notes associated with the event.

    Main attributes:

    - list_: list of TimestampedAnnotations, sorted by increasing
      timestamps. List-like operations on this list can be performed
      directly on the EventData: len(), subscripting, and
      iteration.

    - cursor: index between annotations (0 = before the first
    annotation, positive). The cursor corresponds to a time between
    the two annotations (their timestamp included, since they can have
    the same timestamp).

    - note: string with the note associated with the event.
    """
    def __init__(self, list_=None, cursor=0):
        """
        list_ -- list of TimestampedAnnotations.

        cursor -- insertion index for the next annotation.
        """
        self.list_ = [] if list_ is None else list_
        self.cursor = cursor
        self.note = ""  # Note associated to the event

    def __len__(self):
        return len(self.list_)

    def __getitem__(self, slice_):
        """
        Return the annotations from the given slice.
        """
        return self.list_[slice_]

    def __iter__(self):
        return iter(self.list_)

    def cursor_at_time(self, timestamp):
        """
        Set the internal cursor so that an annotation at the given
        time would be inserted in timestamp order.

        The cursor is put *after* any annotation with the same time
        stamp.

        timestamp -- the cursor is put between two annotations, so
        that the given timestamp is between their timestamps.
        """
        self.cursor = bisect.bisect(
            [annotation.time for annotation in self.list_], timestamp)

    def next_annotation(self):
        """
        Return the first annotation after the cursor, or None if there
        is none.
        """
        try:
            return self[self.cursor]
        except IndexError:
            return None

    def prev_annotation(self):
        """
        Return the annotation just before the cursor, or None if there
        is none.
        """
        return self[self.cursor-1] if self.cursor >= 1 else None

    def insert(self, annotation):
        """
        Insert the given annotation at the cursor location and moves
        it to after the inserted annotation (so that a next insert()
        on the next annotation in time puts it in the right place in
        the list).

        The cursor must be located so that the insertion is done in
        timestamp order. Using cursor_at_time(annotation.time) does this
        (but this call is not required, as the cursor can be set by
        other means too, including outside of this class).
        """
        self.list_.insert(self.cursor, annotation)
        self.cursor += 1

    def delete_prev(self):
        """
        Delete the annotation just before the cursor and update the
        cursor (which does not move compared to its following
        annotation).

        This annotation must exist.
        """
        self.cursor -= 1
        del self.list_[self.cursor]

    def to_builtins_fmt(self):
        """
        Return a version of the EventData that only uses built-in
        Python types, and which is suitable for lossless serialization
        through json.

        This is the reverse of from_builtins_fmt().
        """

        return {
            "cursor": self.cursor,
            "annotation_list": [timed_annotation.to_builtins_fmt()
                                for timed_annotation in self]
        }

    @classmethod
    def from_builtins_fmt(cls, event_data):
        # !!! This function should be updated anytime the annotation saving
        # in Shell.do_save() is updated.
        """
        Reverse of to_builtins_fmt().

        event_data -- event data in the form returned by to_builtins_fmt().
        """
        return cls(
            cursor=event_data["cursor"],
            list_=[
                TimestampedAnnotation.from_builtins_fmt(annotation)
                for annotation in event_data["annotation_list"]
            ],
            note=event_data["note"]
        )

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__qualname__,
                                self.to_builtins_fmt())

def cancel_sched_events(scheduler, events):
    """
    Cancel the scheduled events (except getting the next user key) and
    empties their list.

    events -- list of events, where each event was returned by a
    sched.scheduler. Some events can be already passed.
    """
    for event in events:
        try:
            # Highlighting events are not tracked, so they
            # might have passed without this program knowing
            # it, which makes the following fail:
            scheduler.cancel(event)
        except ValueError:
            pass
    events.clear()

def real_time_loop(stdscr, curr_event_ref, start_time, annotations,
                   meaning_history, key_assignments):
    """
    Run the main real-time annotation loop and return the annotation
    time at the time of exit.

    Displays and updates the given annotation list based on
    single characters entered by the user.

    stdscr -- curses.WindowObject for displaying information.

    curr_event_ref -- reference of the event (recording...)  being annotated.

    start_time -- starting annotation time (Time object).

    annotations -- EventData to be updated.

    meaning_history -- history that contains the text of all the
    possible annotations in curr_event_ref, as a mapping from a user
    key to the list of its possible text meanings.

    key_assignments -- mapping that defines each user key: it maps
    current keys to their corresponding index_in_history.
    """

    # Events (get user key, transfer the next annotation to the list
    # of previous annotations) are handled by the following scheduler:
    scheduler = sched.scheduler(time.monotonic)

    ####################
    # Basic settings for the terminal:

    ## The terminal's default is better than curses's default:
    curses.use_default_colors()
    ## For looping without waiting for the user:
    stdscr.nodelay(True)
    ## No need to see any cursor:
    curses.curs_set(0)
    ## No need to have a cursor displayed at its position:
    stdscr.leaveok(True)

    ####################
    # Initializations:


    ## Terminal size:
    (term_lines, term_cols) = stdscr.getmaxyx()

    # !!! POSSIBLE FEATURE: Window resizing could be handled, with
    # signal.signal(signal.SIGWINCH, resize_handler). This would
    # involve drawing the screen again.

    def addstr_width(y, x, text, attr=curses.A_NORMAL):
        """
        Like stdscr.addstr, but truncates the string so that it does not
        go beyond the last column, and so that there is no line
        wrapping unless explicit.

        text -- string with the text to be displayed. The only newline
        can be at the end, and it might be removed if it is too far on
        the right.
        """
        stdscr.addstr(y, x, text[:term_cols-1-x], attr)

    ## Annotations cursor:
    annotations.cursor_at_time(start_time)

    ####################
    # Information display at start:

    stdscr.clear()

    addstr_width(0, 0, "Event:", curses.A_BOLD)
    addstr_width(0, 7, curr_event_ref)

    stdscr.hline(1, 0, curses.ACS_HLINE, term_cols)

    addstr_width(2, 0, "Next annotation:", curses.A_BOLD)

    addstr_width(3, 0, "Annotation timer:", curses.A_BOLD)

    stdscr.hline(4, 0, curses.ACS_HLINE, term_cols)

    # Help at the bottom of the screen:
    help_start_line = term_lines - (len(key_assignments)+6)
    stdscr.hline(help_start_line, 0, curses.ACS_HLINE, term_cols)
    addstr_width(help_start_line+1, 0, "Commands:\n", curses.A_BOLD)
    stdscr.addstr("<Space>: return to shell\n")
    stdscr.addstr("<Del>/-: delete previous annotation / value\n")
    stdscr.addstr("<4 arrows>, <, >: navigate (annotations and time)\n")
    for (key, index) in key_assignments.items():
        stdscr.addstr("{} {}\n".format(key, meaning_history[key][index]))
    stdscr.addstr("0-9: sets the value of the previous annotation")

    ## Previous annotations:

    ## Scrolling region (for previous annotations):
    stdscr.scrollok(True)
    # Maximum number of previous annotations in window:
    prev_annot_height = help_start_line-6
    if prev_annot_height < 2:
        # !! If the following is a problem, the help could be
        # optionally removed OR displayed with a special key, possibly
        # even as a window that can appear or disappear.
        raise TerminalNotHighEnough

    stdscr.setscrreg(6, 5+prev_annot_height)

    addstr_width(5, 0, "Previous annotations:", curses.A_BOLD)

    ####################
    # Synchronization between the annotation timer, the scheduler
    # timer and the player timer:

    # Counters for the event scheduling:
    start_counter = time.monotonic()

    # Starting the player is better done close to setting
    # start_counter, so that there is no large discrepancy between
    # the time in the player and this time measured by this
    # function:
    player_module.start()

    def time_to_counter(timestamp):
        """
        Return the scheduler counter corresponding to the given
        annotation timestamp.

        timestamp -- time (datetime.timedelta, including Time).
        """
        return (timestamp-start_time).total_seconds() + start_counter

    def counter_to_time(counter):
        """
        Return the annotation timestamp corresponding to the given
        scheduler counter.

        counter -- scheduler counter (in seconds).
        """
        return start_time + datetime.timedelta(seconds=counter-start_counter)

    ####################
    # Display of annotations

    # Annotations require times from the annotation timer, so this
    # comes after setting the timers above.

    # Utility for convenient displaying the text associated to (the
    # internal form of) annotation:
    def annot_str(ts_annotation):
        """
        Return a string version of given time-stamped annotation, based on
        the history in meaning_history.

        ts_annotation -- TimestampedAnnotation.
        """
        (timestamp, annotation) = (ts_annotation.time,
                                   ts_annotation.annotation)

        (key, index) = annotation
        meaning = meaning_history[key][index]

        value_str = (" [{}]".format(ts_annotation.value)
                     if hasattr(ts_annotation, "value")
                     else "")

        return "{} {}{}".format(timestamp, meaning, value_str)

    # In order to cancel upcoming updates of the next annotation
    # (highlight and transfer to the list of previous events), the
    # corresponding events are stored in this list:
    cancelable_events = []

    def display_annotations():
        # !! This function is only here so that the code be more organized.
        """
        Display the list of previous annotations, and the next annotation.

        Schedule the next annotation list update (with the next
        annotation going from the next annotation entry to the
        previous annotations list).

        The lines used for the display must be empty before calling
        this function.
        """

        # Previous annotations:

        ## If there is any annotation before the current time:
        if annotations.cursor:  # The slice below is cumbersome otherwise

            slice_end = annotations.cursor-1-prev_annot_height
            if slice_end < 0:
                slice_end = None  # For a Python slice

            for (line_idx, annotation) in enumerate(
                    annotations[annotations.cursor-1 : slice_end :-1], 6):

                addstr_width(line_idx, 0, annot_str(annotation))
                # stdscr.clrtoeol()  # For existing annotations

        # else:
        #     line_idx = 5  # Last "written" line

        # # The rest of the lines are erased:
        # for line_idx in range(line_idx+1, 5+prev_annot_height):
        #     stdscr.move(line_idx, 0)
        #     stdscr.clrtoeol()

        display_next_annotation()

    def display_next_annotation():
        """
        Display the next annotation.

        Its highlighting and next scrolling down are scheduled (and
        any previously scheduled highlighting and scrolling down is
        canceled).

        The previous annotation list must be displayed already.
        """

        next_annotation = annotations.next_annotation()

        # Coordinate for the display (aligned with the running timer):
        x_display = 19

        # Display
        next_annotation_text = (
            annot_str(next_annotation)
            if next_annotation is not None else "<None>")

        addstr_width(2, x_display, next_annotation_text)
        stdscr.clrtoeol()

        nonlocal cancelable_events

        # Any queued event must be canceled, as they are made
        # obsolete by the handling of the next annotation
        # highlighting and scrolling below:
        cancel_sched_events(scheduler, cancelable_events)

        if next_annotation is not None:

            cancelable_events = [

                # Visual clue about upcoming annotation:
                scheduler.enterabs(
                    # The chosen delay must be larger than the time
                    # that it takes for the user to add a value to an
                    # annotation (otherwise, he would not always have
                    # enough time to target the previous annotation
                    # and change its value before it is replaced by
                    # the next annotation).
                    time_to_counter(next_annotation.time)-1, getkey_priority-1,
                    lambda: stdscr.chgat(
                        2, x_display,
                        len(next_annotation_text), curses.A_STANDOUT)),

                # The event scrolling must be scheduled *before*
                # checking for a user key, because it is a requirement
                # of getkey() that any annotation *at* or before the
                # next_getkey_counter is in the list of previous
                # annotation list.


                # The transfer of next_annotation will require the
                # list of previous annotations to be displayed:
                scheduler.enterabs(time_to_counter(next_annotation.time),
                                   getkey_priority-1, scroll_forwards)
                ]

    def scroll_forwards():
        """
        Move the annotations forwards in time.

        The current next annotation is moved to the list of previous
        annotations, and the next annotation (if any) is updated.  The
        screen is then refreshed.

        The annotation cursor is moved forward, and the next scrolling
        is scheduled (if necessary).

        A next annotation must be present (both on screen and in
        annotations, in a consistent way) when calling this function.
        """

        # Transfer on screen to the list of previous annotations:
        #
        # This requires the previous annotations to be already displayed:
        stdscr.scroll(-1)
        addstr_width(6, 0, annot_str(annotations.next_annotation()))

        # The cursor in the annotations list must be updated to
        # reflect the screen update:
        annotations.cursor += 1

        display_next_annotation()

        stdscr.refresh()  # Instant feedback


    def scroll_backwards(only_scroll_previous=False):
        """
        Move the annotations backwards in time.

        Scroll the list of previous annotations backwards in time
        once, and the next annotation (if any) is updated. The screen
        is then refreshed.

        The annotation cursor is moved backwards once, and the next
        scrolling is scheduled.

        There must be an annotation before the cursor when calling
        this function.

        only_scroll_previous -- if true, only the list of previous
        annotations is scrolled (the next annotation is not updated,
        and the annotation cursor is not updated either). This case is
        useful for updating the list of previous annotations after
        deleting the annotation before the cursor.
        """

        if not only_scroll_previous:
            # Corresponding cursor movement:
            annotations.cursor -= 1
            display_next_annotation()

        stdscr.scroll()

        # The last line in the list of previous annotations might have
        # to be updated with an annotation that was not displayed
        # previously:
        index_new_prev_annot = annotations.cursor-prev_annot_height
        if index_new_prev_annot >= 0:
            addstr_width(5+prev_annot_height, 0,
                         annot_str(annotations[index_new_prev_annot]))

        # Instant feedback:
        stdscr.refresh()

    def navigate(key, key_time, time_sync, annotations):
        """
        Given a navigation key entered at the given time for the given
        annotations, update the annotation time and screen.

        Beeps are emitted for impossible operations (like going to the
        previous annotation when there is none).

        key -- KEY_RIGHT, KEY_LEFT or KEY_DOWN. KEY_RIGHT goes to the
        next annotation, if any. KEY_LEFT goes to the previous
        annotation, if any, or two annotations back, if key_time is
        close to the previous annotation. KEY_DOWN goes back NAVIG_STEP
        in time.

        key_time -- time at which the key is considered
        pressed (compatible with a datetime.timedelta).

        time_sync -- function that takes a new Time for the annotation
        timer and synchronizes the scheduler counter with it, along
        with the external player play head time.

        annotations -- EventData which is navigated through the
        key. Its cursor must be where key_time would put it with
        cursor_at_time(), i.e.  .prev_annotation().time <= key_time <
        .next_annotation().time.
        """
        # It is important to synchronize the times early: otherwise,
        # time scheduling is broken (like for instance the automatic
        # scrolling of annotations). This is why the screen display is
        # only run after performing the time synchronization.

        if key == "KEY_RIGHT":

            next_annotation = annotations.next_annotation()
            if next_annotation is not None:
                time_sync(next_annotation.time)
                scroll_forwards()
            else:
                curses.beep()

        elif key == "KEY_LEFT":

            # Where is the previous annotation?
            prev_annotation = annotations.prev_annotation()

            if prev_annotation is None:
                curses.beep()
            else:

                prev_annot_time = prev_annotation.time

                # In order to allow the user to move beyond just the
                # previous annotation, there is a small time window
                # after each annotation during which going backwards
                # moves *two* annotations back. In effect, this skips
                # the previous annotation and goes back to the one
                # before (if any):
                if key_time-prev_annot_time < REPEAT_KEY_TIME:

                    if annotations.cursor > 1:
                        # There is an annotation before the previous
                        # one: we go there:
                        time_sync(annotations[annotations.cursor-2].time)
                        scroll_backwards()
                    else:
                        # It is not possible to go before the first
                        # annotation, with KEY_LEFT, since it jumps to
                        # the previous annotation:
                        curses.beep()

                else:
                    time_sync(prev_annot_time)
                    # It is important to update the Next annotation
                    # events, if any, since the user sees them in the
                    # annotation timer time, but they are scheduled in
                    # the old scheduler time:
                    display_next_annotation()

        else:  # KEY_DOWN or KEY_UP

            if key == "KEY_UP":

                # Time to be reached:
                target_time = key_time + NAVIG_STEP

                # Function for moving to the next annotation *in the
                # chosen direction*:
                next_annot = annotations.next_annotation

                # Screen update for going to the next annotation *in
                # the chosen direction*:
                scroll = scroll_forwards

                def must_scroll(time_):
                    """
                    Return true if scrolling is needed in order to reach a
                    situation where the next and previous annotations
                    are correctly displayed.

                    time_ -- time stamp of an annotation in the Next
                    annotation field.
                    """
                    # Any annotation at the same time as the
                    # annotation timer must be in the list of previous
                    # annotations, in order to satisfy the getkey()
                    # requirement:
                    return time_ <= target_time

            else:  # KEY_DOWN:

                target_time = key_time - NAVIG_STEP
                next_annot = annotations.prev_annotation
                scroll = scroll_backwards
                def must_scroll(time_):
                    """
                    time_ -- time stamp of the latest previous annotation
                    displayed on screen.
                    """
                    #
                    return time_ > target_time

            # The previous annotations are passed one by one (because
            # the screen update uses scroll_*(), which moves by one
            # annotation), so as to reach target_time:
            while True:

                # Next annotation in the considered direction:
                annotation = next_annot()

                if annotation is None:
                    break

                annotation_time = annotation.time

                if must_scroll(annotation_time):
                    # The annotation must be passed over:
                    time_sync(annotation_time)
                    scroll()
                else:
                    break

            time_sync(target_time)
            display_next_annotation()

    ####################
    # User key handling:

    # Counter for the next getkey() (see below). This counter is
    # always such that the annotations.cursor corresponds to it
    # (with respect to the annotation times in annotations): the
    # two are always paired.
    next_getkey_counter = start_counter

    def time_sync(new_time):
        """
        Update the synchronization between the annotation
        timer and the scheduler counter, and with the
        external player time.

        new_time -- new annotation time (Time object).
        """
        nonlocal start_time, start_counter
        start_time = new_time
        start_counter = next_getkey_counter
        player_module.set_time(*new_time.to_HMS())

    # Priority of getkey() for the scheduler:
    getkey_priority = 1

    def getkey():
        """
        Get the user command (if any) and process it.

        Before doing this, refreshes the screen, and schedules
        the next key check.

        This event is always scheduled for the next_getkey_counter
        scheduler counter, with a priority of getkey_priority.

        It is guaranteed that the next annotation has a time stamp
        strictly after the next_getkey_counter time. Similarly, the
        list of previous annotations contains annotations that have a
        time stamp *at or* before the next_getkey_counter time.
        """

        # !! The guarantee in case of a next_getkey_counter that falls
        # precisely on one or more annotations is important, as the
        # program must know in what state the screen is so as to
        # update it correctly.
        #
        # !! Maybe it would make sense to put the timer
        # synchronization management in a Timer object, that would
        # make the timing model explicit.

        nonlocal next_getkey_counter

        # !!! POSSIBLE FEATURE: Let the user decide what KEY_LEFT and
        # KEY_RIGHT do: jump to the previous/next annotation, *of a
        # certain type or not*. This would be useful, for example, for
        # going from "bookmark" to bookmark (user bookmark, start of a
        # music piece, etc.).

        # !!! POSSIBLE FEATURE: Stop the timers *while allowing the
        # user to move through annotations*. This can be useful for
        # editing them (currently, the piece keeps playing and the
        # annotations scrolling, which is not completely comfortable).

        # !!! Test with annotations that are at the exact same
        # time. This probably works, because the scheduler handles
        # events in priority order: two scrollings will be performed
        # before checking if the user types the next key, so
        # everything should work.

        # Current time in the annotation process:
        annotation_time = counter_to_time(next_getkey_counter)
        addstr_width(3, 19, str(annotation_time))
        stdscr.clrtoeol()  # The time can have a varying size

        try:
            key = stdscr.getkey()
        except curses.error:
            key = None  # No key pressed
        else:

            try:
                # Annotation, in the internal format [key,
                # index_in_meaning_history]:
                user_annotation = [key, key_assignments[key]]
            except KeyError:

                if key.isdigit():
                    prev_annotation = annotations.prev_annotation()
                    if prev_annotation is not None:
                        prev_annotation.set_value(int(key))
                        # The screen must be updated so as to reflect
                        # the new value:
                        addstr_width(6, 0, annot_str(prev_annotation))
                        stdscr.clrtoeol()
                        stdscr.refresh()  # Instant feedback
                    else:  # No previous annotation
                        curses.beep()
                elif key == "\x7f":
                    # ASCII delete: delete the previous annotation
                    if annotations.cursor:  # Any previous annotation?
                        annotations.delete_prev()
                        scroll_backwards(only_scroll_previous=True)
                    else:
                        curses.beep()  # Error: no previous annotation
                elif key in {"KEY_RIGHT", "KEY_LEFT", "KEY_DOWN", "KEY_UP"}:

                    # Navigation:

                    navigate(key, counter_to_time(next_getkey_counter),
                             time_sync, annotations)

                elif key == "-":  # Delete value (if any)
                    prev_annotation = annotations.prev_annotation()
                    if prev_annotation is None:
                        curses.beep()
                    else:
                        try:
                            del prev_annotation.value
                        except AttributeError:
                            curses.beep()  # No value
                        else:
                            # The display of the last annotation must
                            # be updated:
                            addstr_width(6, 0, annot_str(prev_annotation))
                            stdscr.clrtoeol()
                            stdscr.refresh()

                elif key in {"<", ">"}:  # Go to the first/last annotation:

                    if key == ">":
                        next_annotation = annotations.next_annotation
                        scroll = scroll_forwards
                        last_annotation = annotations.prev_annotation
                    else:  # "<"
                        next_annotation = annotations.prev_annotation
                        scroll = scroll_backwards
                        last_annotation = annotations.next_annotation

                    while next_annotation() is not None:
                        # !! The scrolling could be optimized by
                        # removing refresh instructions, or even by
                        # deciding to repaint the whole screen if the
                        # jump is long.
                        scroll()

                    # Timer update:
                    current_annotation = last_annotation()
                    if current_annotation is not None:
                        time_sync(current_annotation.time)
                    else:
                        curses.beep()  # No annotations

                elif key == " ":
                    # Quitting is handled later, but space is still a
                    # valid key (no beep):
                    pass
                else:
                    curses.beep()  # Unknown key

            else:  # A user annotation key was given:

                annotations.insert(TimestampedAnnotation(
                    annotation_time, user_annotation))
                # Display update:
                stdscr.scroll(-1)
                addstr_width(6, 0, annot_str(annotations.prev_annotation()))
                stdscr.refresh()  # Instant feedback

        # Looping through the scheduling of the next key check:
        if key == " ":

            # Stopping the player is best done as soon as possible, so
            # as to keep the synchronization between
            # self.curr_event_time and the player time as well as
            # possible, in case player_module.set_time() is a no-op
            # but player_module.stop() works:
            player_module.stop()

            # No new scheduling of a possible user key reading.

            # Existing scheduled events (highlighting and transfer of
            # the next annotation to the previous annotations) must be
            # canceled (otherwise the scheduler will not quit because
            # it has events waiting in the queue):
            cancel_sched_events(scheduler, cancelable_events)

        else:
            next_getkey_counter += 0.1  # Seconds
            # Using absolute counters makes the counter more
            # regular, in particular when some longer
            # tasks take time (compared to using a
            # relative waiting time at each iteration of
            # the loop).
            scheduler.enterabs(next_getkey_counter, getkey_priority, getkey)

    display_annotations()
    scheduler.enterabs(next_getkey_counter, getkey_priority, getkey)
    scheduler.run()

    # The pause key was entered at the last next_getkey_counter, so
    # this is the time used for updating the event timer:
    getkey_time = counter_to_time(next_getkey_counter)
    player_module.set_time(*getkey_time.to_HMS())  # Explicit synchronization
    return getkey_time

def key_assignments_from_file(file_path):
    """
    Return the key assignments found in the given file, as a
    collections.OrderedDict mapping each key to its text meaning.

    The file syntax and semantics are detailed in
    AnnotateShell.do_load_keys().

    This function is meant to be primarily used from
    AnnotateShell.do_load_keys().

    file_path -- file path, as a string.
    """

    # It is useful to keep the annotations in the same order as in the
    # file: the user can more easily recognize their list.
    key_assignments = collections.OrderedDict()

    with open(file_path) as keys_file:
        for (line_num, line) in enumerate(keys_file, 1):

            line = line.rstrip()

            # Empty lines and comments are skipped:
            if not line or line.startswith("#"):
                continue

            # Some characters are reserved and therefore cannot be
            # chosen by the user. The text meaning cannot be empty:
            # otherwise, some annotations would look empty, when
            # displayed during the "annotate" command process.
            match = re.match("([^\s0-9<>\x7f\-])\s*(.+)", line)
            if not match:
                raise Exception("Syntax error on line {}:\n{}".format(
                    line_num, line))

            (key, text) = match.groups()

            # Sanity check, for the benefit of the user:
            if key in key_assignments:
                raise Exception("Key defined more than once: {}.".format(key))
            key_assignments[key] = text

    return key_assignments

def to_v2_1_data(file_contents):
    """
    Update the contents read from an pre-v2 annotation file by
    converting it to the v2.1 form of the contents.

    The "format_version" entry is not set, though (as the version is
    known to be the latest version).
    """

    # key_assignments is of the form: [ [description_string, key],
    # […],… ]. It is updated so that each key is mapped to the
    # (1-element) list of possible meanings:

    # Creation of history of key assignments:
    old_key_assignments = file_contents.pop("key_assignments") or []

    file_contents["meaning_history"] = {
        key: [meaning]
        for (meaning, key) in old_key_assignments}

    # Each key in annotations should now be assigned
    # meaning #0:
    for event_data in file_contents["annotations"].values():
        for annotation in event_data["annotation_list"]:
            # annotation = [time_stamp, annotation_contents_array]
            annotation[1][0] = [annotation[1][0], 0]  # Meaning #0 of the key

    # New key assignments: each key is associated to its meaning index:
    file_contents["key_assignments"] = collections.OrderedDict([
        (meaning_key[1], 0)  # Meaning #0 is the current meaning
        for meaning_key in old_key_assignments])

class AnnotateShell(cmd.Cmd):
    """
    Shell for launching a real-time annotation recording loop.
    """
    # IMPORTANT: do_*() and complete_*() methods are called
    # automatically through cmd.Cmd.

    intro = ("Use <Tab> for automatic completion.\n"
             "Command history: up/down arrows, and Ctrl-R for searching.\n"
             "Type ? (or help) for help.")

    prompt = ">>> "

    def __init__(self, annotations_path):
        """
        Handle the modification of the given annotation file.

        The program exits with an error code if the annotations_path file is
        already locked.

        annotations_path -- pathlib.Path to the file with the annotations.
        """

        print()

        super().__init__()

        self.annotations_path = annotations_path

        # Current event to be annotated. This is a key of self.all_annotations,
        # if not None:
        self.curr_event_ref = None

        # Some attributes are defined and then possibly updated: this allows
        # the type or value of these attributes to be automatically correct
        # whether the attributes are read from an existing annotations file or
        # created (as empty data with a specific type) from a new annotation
        # file.

        # Mapping of each keyboard key to the index of its meaning in the key
        # history:
        self.key_assignments = collections.OrderedDict()
        # Annotations associated to each event reference:
        self.all_annotations = collections.defaultdict(EventData)
        self.bookmarks = {}

        if annotations_path.exists():  # Existing annotations

            # A lock is acquired before any change is made to the in-memory
            # annotation data, so that subsequent writes of the data to disk are
            # not replaced by the annotations from another instance of this
            # program.
            #
            # Locking before parsing the file gives a faster feedback to the
            # user.
            self.lock_annotations_path_or_exit()
            
            with annotations_path.open() as annotations_file:
                # Using object_hook in order to immediately transform JSON
                # structures into the internal data format would not be robust:
                # this could break when the file format gets updated, because
                # the transformations are generally format-specific.
                file_contents = json.load(annotations_file)

            ## Format update. The update is done at (parsed) JSON level so
            ## as to not handle format updates in many places in the code
            ## (e.g., the data associated to an event could handle a missing
            ## event note from a format before 2.2, etc.). Also, in the longer
            ## term, older formats could be made obsolete, and only the
            ## format update here could be removed from the code:

            # If we have a file in the pre-v2 format, it is converted
            # to the current version of the JSON data:
            if "format_version" not in file_contents:
                to_v2_1_data(file_contents)

            if file_contents["format_version"] < [2, 2]:
                # Format 2.2 introduced event notes:
                for event_data in file_contents["annotations"]:
                    event_data["note"] = ""

            # Internal representation of the necessary parts of the
            # file contents:

            self.meaning_history = file_contents["meaning_history"]

            self.key_assignments.update(file_contents["key_assignments"])

            # Mapping from each event to its annotations, which are stored
            # as an EventData:
            self.all_annotations.update({
                event_ref: EventData.from_builtins_fmt(
                    annot_with_cursor)
                for (event_ref, annot_with_cursor)
                in file_contents["annotations"].items()})

            try:
                self.bookmarks.update(file_contents["bookmarks"])
            except KeyError:  # Bookmarks introduced in the v2.1 format
                pass
            else:
                # Conversion of times to the internal format:
                for location in self.bookmarks.values():
                    # location = [event reference, time]:
                    location[1] = Time.from_HMS(location[1])

            self.do_list_events()
            print()
            self.do_list_bookmarks()

        else:  # A new file must to be created
            self.meaning_history = {}  # No key meanings
            # It is useful to lock the annotation file, or two instances
            # of this program could run on the same new path and later
            # clobber it:
            self.do_save()

        print()

        # Automatic (optional) saving of the annotations, both for
        # regular exit and for exceptions:
        def save_if_needed():
            """
            Save the updated annotations if wanted.
            """
            print()
            if input("Do you want to save the annotations and key"
                     " assignments (y/n)? [y] ") != "n":
                self.do_save()
        atexit.register(save_if_needed)

    def cmdloop_no_interrupt(self):
        """
        Like cmdloop(), but mimics the usual Unix shell behavior of Ctrl-C.

        When the user presses Ctrl-C, a new prompt appears.

        This prevents users from having to quit the program when typing
        Ctrl-C, as they can expect the same behavior as in most Unix shells.
        """
        print(self.intro)
        while True:
            try:
                super().cmdloop(intro="")  # Executes preloop() and postloop()
            except KeyboardInterrupt:
                print("^C")
            else:  # Normal exit of the command loop
                break

    def lock_annotations_path_or_exit(self):
        """
        Lock the annotations file or exit with an error message.

        The annotations file path is self.annotations_path, which must be
        defined.
        """
        try:
            self._annotation_file_lock = lock_file(self.annotations_path)
        except FileLocked:
            sys.exit("Quitting because another instance of this program is"
                     " running on the same annotation file. This prevents"
                     " unwanted inconsistent modifications of the annotation"
                     " file.")

    def update_key_history(self, key_assignments):
        """
        Merge key assignments with the history of key assignments, which
        is updated.

        Return a mapping from each key in key_assignments to its index
        in the meaning history (self.meaning_history), with items in
        the same order as in key_assignments.

        key_assignments -- key assignments as returned by
        key_assignments_from_file().
        """

        assignment_indexes = collections.OrderedDict()

        for (key, text) in key_assignments.items():

            # Possible new key:
            history = self.meaning_history.setdefault(key, [text])

            try:
                history_index = history.index(text)
            except ValueError:  # New text
                history_index = len(history)
                history.append(text)

            assignment_indexes[key] = history_index

        return assignment_indexes

    @property
    def curr_event_time(self):
        """
        Time of the annotation timer.
        """
        return self._curr_event_time

    @curr_event_time.setter
    def curr_event_time(self, curr_event_time):
        """
        Set both the annotation timer for the current event, and the
        player play head to the given time.

        curr_event_time -- Time object.
        """
        self._curr_event_time = curr_event_time
        player_module.set_time(*curr_event_time.to_HMS())

    def emptyline(self):
        pass  # No repetition of the last command

    def help_save(self):
        """User documentation for the "save" command."""
        print(
            "Save the current annotations to file after making a copy of any\n"
            "previous version.\n\n"
            "If no previous version was available, a new file is created.")

    def do_save(self, _=None):
        # !!! This function must be updated each time the internal data
        # changes in a way that can be reflected in the saved data (e.g.
        # when adding some new data to an event).
        """
        Do what help_save() prints.

        The new annotations file is then locked or the program exits
        with an error code.
        """

        # The new annotations file is first stored as a temporary
        # file: this has the advantage of leaving the current
        # annotation file untouched, which helps should any problem
        # arise. This is better than starting by backing up the
        # current annotation file and then overwriting it, as this
        # could yield a corrupt annotation file.

        annotations_file = tempfile.NamedTemporaryFile('w', delete=False)

        # The internal, more convenient data structure (with
        # TimestampedAnnotation objects, etc.), is converted into
        # a simple structure for the JSON output.

        def encode(obj):
            """
            Encode obj into a JSON-encodable object.

            obj -- object that can't be serialized by the json module.
            """
            if isinstance(obj, Time):
                return obj.to_HMS()
            if isinstance(obj, EventData):
                return obj.to_builtins_fmt()
            # Non-serializable objects would be serialized as None, without
            # the warning below:
            sys.exit("Internal error: serialization of {} required."
                     .format(type(obj)))

        json.dump({
            # !!! The version must be bumped each time more data is
            # added to what is saved, in particular (e.g. addition of a note
            # to an event):
            "format_version": [2, 2],
            "meaning_history": self.meaning_history,
            "annotations": self.all_annotations,
            # Order preservation:
            "key_assignments": list(self.key_assignments.items()),
            "bookmarks": self.bookmarks
            },
            annotations_file,
            default=encode, indent=2)

        annotations_file.close()

        if self.annotations_path.exists():
            # The old annotations are backed up:
            backup_path = self.annotations_path.with_suffix(".json.bak")
            self.annotations_path.rename(backup_path)
            print("Previous annotations moved to {}.".format(backup_path))
        else:
            # A new file must be created:
            print("New annotation file created.")

        # The new annotations file is moved in place:
        shutil.move(annotations_file.name, self.annotations_path)

        print("Annotations (and key assignments) saved to {}."
              .format(self.annotations_path))

        # We cannot further modify the in-memory annotation unless this process
        # gets a lock on the new annotations file, because it will typically be
        # written over later:
        self.lock_annotations_path_or_exit()

    def do_exit(self, _=None):
        """
        Exit this program and optionally save the annotations.
        """
        # The handling of the optional, final saving of the updated
        # annotations is handled by an atexit handler:
        return True  # Quit

    # def do_EOF(self, arg):
    #     return self.do_exit(arg)
    # do_EOF.__doc__ = do_exit.__doc__

    def do_set_time(self, time_):
        """
        Set the current annotation timer to the given time.

        If a player is used, then the timer is also set in the player,
        which typically sets the play head location.

        time_ -- time string in S, M:S or H:M:S format.
        """

        try:
            # No need to have the program crash and exit for a small error:
            time_parts = list(map(float, time_.split(":", 2)))
        except ValueError:
            print("Incorrect time format. Use M:S or H:M:S.")
        else:
            self.curr_event_time = Time.from_HMS(time_parts)

            print("Annotation timer set to {}.".format(self.curr_event_time))

    def do_load_keys(self, file_path):
        """
        Load key assignments from the given file so that they can be used
        (they replace previous key assignments). They are saved along
        with the annotations.

        The file format is as follows:

        # Musical annotations

        s    start (between pieces, before the beginning)
        e    end (0 = could be an end if needed)
        ...

        The first letter is a character (case sensitive). Typing this
        character will insert the annotation described afterwards (free
        text).

        The key is followed by the text describing the meaning of the
        annotation (and optionally of any numeric modifier). Leading
        and trailing spaces in the annotation are ignored.

        Empty lines and lines starting by # are ignored.
        """

        # Common error (for the command-line usage): no file name
        # given:
        if not file_path:
            print("Please provide a file path.")
            return

        try:
            key_assignments = key_assignments_from_file(file_path)
        except Exception as exc:
            print("Error: {}".format(exc))
            return

        print("Key assignments loaded from file {}.".format(file_path))

        # The key definitions are merged in the history of
        # definitions:
        self.key_assignments = self.update_key_history(key_assignments)

        self.do_list_keys()

    def complete_load_keys(self, text, line, begidx, endidx):
        """
        Complete the text with paths from the current directory.
        """

        # The escape() takes care of characters that are
        # interpreted by glob(), like *:
        return glob.glob("{}*".format(glob.escape(text)))

    def do_annotate(self, arg):
        """
        Immediately start recording annotations for the current
        event reference. This event must first be set with
        set_event.

        The annotation file must also contain annotation key
        definitions. This typically has to be done once after creating
        the file, with the command load_keys.
        """

        if self.key_assignments is None:
            print("Error: please load key assignments first (load_keys"
                  " command).")
            return

        if self.curr_event_ref is None:
            print("Error: please select an event to be annotated",
                  "with set_event.")
            return

        try:
            # The real-time loop displays information in a curses window:
            self.curr_event_time = curses.wrapper(
                real_time_loop, self.curr_event_ref, self.curr_event_time,
                self.all_annotations[self.curr_event_ref],
                self.meaning_history,
                self.key_assignments)

        except TerminalNotHighEnough:
            print("Error: the terminal is not high enough.")
        else:
            print("Stopped annotating event {}.".format(self.curr_event_ref))
            print("Current timestamp: {}.".format(self.curr_event_time))

    def do_list_events(self, event_regex=""):
        """
        List annotated events.

        Without parameter, lists all events.

        With a parameter, only lists events whose name matches the given
        regular expression (which is searched anywhere in the name).
        """

        if self.all_annotations:

            try:
                matching_name = re.compile(event_regex).search
            except re.error as exc:
                print("Incorrect event name regular expression:")
                print(exc)
                return

            print("Annotated events (sorted alphabetically,"
                  " followed by the number of annotations):")
            for event_ref in sorted(self.all_annotations):
                if matching_name(event_ref):
                    print("{} {} [{}]".format(
                        "*" if event_ref == self.curr_event_ref else "-",
                        event_ref, len(self.all_annotations[event_ref])))
        else:
            print("No annotated event found.")

    def do_list_keys(self, _=None):
        """
        List the key assignments for annotations (loaded by load_keys and
        saved in the annotation file).
        """
        if self.key_assignments:
            print("Annotation keys:")
            for (key, index) in self.key_assignments.items():
                print("{} {}".format(key, self.meaning_history[key][index]))
        else:
            print("No defined annotation keys.")

    def do_list_key_history(self, _=None):
        """
        List the history of all key assignments found in the annotation
        file (in alphabetical order, irrespective of the case).
        """
        print("Annotation key history:")
        for key in sorted(self.meaning_history, key=str.lower):
            meanings_iter = iter(self.meaning_history[key])
            print("{} {}".format(key, next(meanings_iter)))
            for addtl_meaning in meanings_iter:
                print("  {}".format(addtl_meaning))

    def do_set_event(self, event_ref=""):
        """
        Set the given event reference as the current event.

        If the event does not exist yet, it is created.

        The current list of references can be obtained with
        list_events.

        If no reference is given, the currently selected event is listed.

        The next annotations will be attached to this event.
        """

        if not event_ref:  # Can be  the empty string if no reference is given
            if self.curr_event_ref is None:
                print("No event currently selected.")
            else:
                print("Currently selected event: {}."
                      .format(self.curr_event_ref))
                print("Annotation timer set to {}."
                      .format(self.curr_event_time))
            return

        self.curr_event_ref = event_ref

        # Annotation list for the current event:
        annotations = self.all_annotations[event_ref]
        print("Current event set to {}.".format(event_ref))
        print("{} annotations found.".format(len(annotations)))

        prev_annotation = annotations.prev_annotation()

        # The time of the previous annotation before the cursor is
        # "just" before when the user last stopped:
        #
        # !!!! It would be nice to save the timer's time instead of
        # the cursor. However, an EventData does not have the
        # concept of current time. This means that the current time
        # for each event should be saved and stored separately. This
        # could be done, instead of storing the EventData cursor
        # into the annotation file.
        if prev_annotation is not None:
            self.curr_event_time = prev_annotation.time
            print("Back to the previous annotation.")
        else:
            self.curr_event_time = Time()

        print("Annotation timer set to {}."
              .format(self.curr_event_time))

    def complete_set_event(self, text, line, begidx, endidx):
        """
        Complete event references with the known references.
        """

        return [
            event_ref
            for event_ref in sorted(self.all_annotations)
            if event_ref.startswith(text)]

    def do_del_event(self, event_ref):
        """
        Delete the given event.
        """

        if event_ref not in self.all_annotations:  # DefaultDict handling
            print('Error: unknown event "{}".'.format(event_ref))
            return

        if self.all_annotations[event_ref] and input(
            'Event "{}" has annotations: really delete (y/n)? [n] '
            .format(event_ref)) != "y":
            
            print('Aborting.')
            return

        del self.all_annotations[event_ref]
        print('Event deleted.')

    complete_del_event = complete_set_event

    def do_rename_event(self, arg):
        """
        Rename the given event.

        Syntax: rename_event Current name -> New name
        """

        # An event renaming must be done in many places: the annotation list,
        # the current event, and bookmarks. It is useful (but not crucial) that
        # the code below do not crash and leave only a partial renaming.
        try:
            current_name, new_name = map(
                lambda name: name.strip(), arg.split("->"))
        except ValueError:
            print("Syntax error. See help rename_event.")
            return

        # Existing events must not be clobbered:
        if new_name in self.all_annotations:
            print('Problem: event "{}" exists. You can delete it if needed.'
                  ' Renaming aborted.'.format(new_name))
            return

        try:
            # Renaming annotations:
            self.all_annotations[new_name] = self.all_annotations.pop(
                current_name)
        except KeyError:
            print('Error: event "{}" not found.'.format(current_name))
            return

        # Renaming the current event: if the currently selected event is the
        # event that was renamed, we consider that the same _event_ should
        # still be selected (and therefore not the same name):
        if self.curr_event_ref == current_name:
            self.curr_event_ref = new_name
            print('Current event is now "{}".'.format(self.curr_event_ref))

        # Renaming of bookmarks:
        for (bookmark_name, bookmark) in self.bookmarks.items():
            if bookmark[0] == current_name:
                bookmark[0] = new_name
                print('Updated event name in bookmark "{}".'
                      .format(bookmark_name))

    complete_rename_event = complete_set_event

    def do_set_bookmark(self, bookmark_name):
        """
        Bookmark the currently selected event and timer.

        Syntax: set_bookmark Bookmark name
        """

        if not bookmark_name:
            print("Error: please provide a bookmark name.")
            return

        if self.curr_event_ref is None:
            print('Error: please first select an event.')
            return
        # As soon as an event is selected, the timer is set, so it is also
        # defined, at this point.
        
        if bookmark_name in self.bookmarks:
            if input("Do you want to replace the bookmark with the same"
                     " name (y/n)? [n] ") != "y":
                print("Aborting.")
                return

        self.bookmarks[bookmark_name] = [
            self.curr_event_ref, self.curr_event_time]

        print('Bookmark "{}" set at event "{}" and timer {}.'
              .format(bookmark_name, *self.bookmarks[bookmark_name]))

    # The completion of bookmark setting uses known bookmarks so that
    # bookmarks can easily be replaced, or so that similar bookmark names
    # can easily be created:
    def complete_set_bookmark(self, text, line, begidx, endidx):
        """
        Complete bookmark name with the known names.
        """

        return [
            bkmk_name
            for bkmk_name in sorted(self.bookmarks)
            if bkmk_name.startswith(text)]

    def do_list_bookmarks(self, _=None):
        """
        List the bookmarks.
        """

        if self.bookmarks:
            print('Bookmarks (sorted alphabetically):')
            for bkmk_key in sorted(self.bookmarks):
                (event_ref, timer) = self.bookmarks[bkmk_key]
                print("- {}: {} {}".format(bkmk_key, event_ref, timer))
        else:
            print('The bookmark list is empty.')

    def do_load_bookmark(self, bookmark_name):
        """
        Load the event and timer value defined by the given bookmark.

        The time is automatically set through the set_time command.
       
        Syntax: load_bookmark Bookmark name
        """
        
        try:
            bookmark = self.bookmarks[bookmark_name]
        except KeyError:
            print('Error: please give an existing bookmark name.')
            return

        # !!!!!!!! It is possible that the new current event does not
        # exist because it was deleted. How to handle this gracefully?
        # "annotate" creates the event. But what about the more general
        # situation? Events are automatically created through a defaultdict.

        (self.curr_event_ref, self.curr_event_time) = bookmark
        # do_set_event(event_ref) would set the timer to the last annotation
        # in the event, and would print the fact that it did, which we don't
        # want here because we set the timer to a specific value.
        self.do_set_event()

    complete_load_bookmark = complete_set_bookmark

    def do_del_bookmark(self, bookmark_name):
        """
        Delete the bookmark with the given name.

        Syntax: del_bookmark Bookmark name
        """
        try:
            deleted_bkmk = self.bookmarks.pop(bookmark_name)
        except KeyError:
            print('Error: no bookmark with this name found.')
        else:
            print('Deleted bookmark "{}" ({} {}).'
                  .format(bookmark_name, deleted_bkmk[0], deleted_bkmk[1]))

    complete_del_bookmark = complete_load_bookmark

    def do_edit_note(self, event_ref=None):
        """
        Edit the note associated with an event.

        If no event is specified, edits the note of the current event, if any.
        Otherwise edits the note of the given event.
        """

        if event_ref is None:
            event_ref = self.curr_event_ref

        # The note is temporarily put in a file.
        # The temporary file has delete=False just as a precaution for
        # Windows, where the editor might not be able to open the
        # file if it is still open by this program, so we keep it after
        # closing:
        with tempfile.namedtemporaryfile("w", delete=false) as note_file:
            # the current note contents must be written to the file:
            note_file.write(self.all_annotations[event_ref].note)

        # !! The list should be extended, for Windows, for instance with
        # "notepad.exe":
        for editor in [os.environ.get("editor", "nano"), "vim", "vi"]:
            # we let the user handle any error from the editor (they are
            # displayed), but we handle the case of an editor that cannot
            # be found:
            try:
                subprocess.run([editor, tmp_file_Name])
            except FileNotFoundError:
                pass
            else:
                break
        else:
            print("Internal error: no editor found.")
            return

        # we get the note:
        with open(note_file.name) as note_file:
            self.all_annotations[event_ref].note = note_file.read()

        print("Note for event {} edited.".format(event_ref))

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(

        "--player", metavar="python_module", action="store",

        help="""
        Name of Python module that controls some real-time player (music
        player, etc.).

        The module must be in the Python module path (working
        directory, directory of this program, etc.)  The module must
        provide a start() and a stop() function (that take no
        argument), and a function set_time(hours, minutes, seconds).
        start() is called when the annotation process starts, stop()
        when it is stopped.  set_time() is called when the user sets
        the time of the annotation timer.  Annotations times can thus
        be synchronized with the elapsed time in a piece of music,
        etc.""")

    parser.add_argument(
        "annotation_file",
        help=("Path to the annotation file (it will be created if it does not"
              " yet exist)"),
        type=pathlib.Path
        )

    args = parser.parse_args()

    player_functions = ["start", "stop", "set_time"]
    if args.player:
        player_module = __import__(args.player, fromlist=player_functions)
    else:  # Default player (which does nothing):
        player_module = sys.modules[__name__]  # This module
        for func_name in player_functions:
            setattr(player_module, func_name, lambda *args, **kwargs: None)

    AnnotateShell(args.annotation_file).cmdloop_no_interrupt()
