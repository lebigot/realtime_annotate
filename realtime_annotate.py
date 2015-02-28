#!/usr/bin/env python3.4

"""
Real-time annotation tool.

Annotations are timestamped. They contain user-defined values.

Optionally, some real-time player (music player, video player, MIDI
player,...) can be controlled so that annotation timestamps are
synchronized with the player (the player time head is automatically
set to the annotation timestamp; the player is started and stopped at
the same times as the annotation process).

(c) 2015 by Eric O. LEBIGOT (EOL)
"""

__version__ = "1.2"
__author__ = "Eric O. LEBIGOT (EOL) <eric.lebigot@normalesup.org>"

# !! The optional player driven by this program must be defined by
# functions in a module stored in a variable named player_module. See
# the main program for two examples.

import collections
import enum
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

# Time interval between keyboard keys that are considered repeated:
REPEAT_KEY_TIME = datetime.timedelta(seconds=1)

class Time(datetime.timedelta):
    # ! A datetime.timedelta is used instead of a datetime.time
    # because the internal scheduler of this program must be added to
    # the current annotation timestamp so as to update it. This cannot
    # be done with datetime.time objects (which cannot be added to a
    # timedelta).
    """
    Timestamp compatible with a datetime.timedelta.
    """

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
    
    def __str__(self):
        """
        ...HH:MM:SS.d format.
        """
        return "{:02}:{:02}:{:04.1f}".format(*self.to_HMS())

class TimestampedAnnotation:
    """
    Annotation made at a specific time.

    Main attributes:
    - time (datetime.timedelta)
    - annotation (enumerated constant)

    A value can be added to the annotation. It is stored in the
    optional 'value' attribute. This is typically used for indicating
    an intensity (such as a small glitch, or a very uninspired
    part). A merit of this approach is that there is no restriction on
    the contents of value (which can be None, etc.). Another merit is
    that only annotations that have a value store one (in memory, on
    disk, etc.).
    """
    def __init__(self, time, annotation):
        """
        time -- timestamp for the annotation, as a datetime.timedelta.
        
        annotation -- annotation to be stored, as an enumerated
        constant.
        """
        self.time = time
        
        # The advantage of storing the annotation as an Enum instead
        # of just a character (enumerated constant) is that it can
        # have a nice string representation (Enum name), and that it
        # preserve the associated character (which can then be saved to a
        # file, etc.):
        self.annotation = annotation
    
    def set_value(self, value):
        """
        Set the annotation's value.
        """
        self.value = value

    def __str__(self):

        # The fact that Enums can have a nice-looking name is
        # convenient:
        result = "{} {}".format(self.time, self.annotation.name)
        
        if hasattr(self, "value"):
            result += " [value {}]".format(self.value)
            
        return result

    def to_builtins_fmt(self):
        """
        Return a version of the annotation with only Python builtin types.

        Returns (time, annot), where annot is [annotation.value] or
        [annotation.value, value], if a value is defined for the
        TimestampedAnnotation. Thus, only the value of the enumeration
        is saved. This allows the enumeration names to be modified
        without touching the annotation.
        """

        annotation = [self.annotation.value]
        if hasattr(self, "value"):
            annotation.append(self.value)
            
        return [self.time.to_HMS(), annotation]



    @classmethod
    def from_builtins_fmt(cls, annotation_kinds, timed_annotation):
        """
        Reverse of to_builtins_fmt().

        annotation_kinds -- enum.Enum for interpreting the
        annotation. The timed_annotation refers to some value in
        the enumeration.

        timed_annotation -- version of the annotation as returned by
        to_builtins_fmt().
        """
        annot = timed_annotation[1]

        result = cls(
            Time(**dict(zip(("hours", "minutes", "seconds"),
                            timed_annotation[0]))),
            annotation_kinds(annot[0]))
        
        if len(annot) > 1:
            result.value = annot[1]
            
        return result
        
class NoAnnotation(Exception):
    """
    Raised when a requested annotation cannot be found.
    """

class TerminalNotHighEnough(Exception):
    """
    Raised when the terminal is not high enough for a proper display.
    """
    
class AnnotationList:
    """
    List of annotations (for a single reference) sorted by timestamp,
    with a live cursor between annotations.

    Main attributes:
    
    - list_: list of TimestampedAnnotations, sorted by increasing
      timestamps. List-like operations on this list can be performed
      directly on the AnnotationList: len(), subscripting, and
      iteration.
    
    - cursor: index between annotations (0 = before the first
    annotation, positive).
    """
    def __init__(self, list_=None, cursor=0):
        """
        list_ -- list of TimestampedAnnotations.
        
        cursor -- insertion index for the next annotation.
        """
        self.list_ = [] if list_ is None else list_
        self.cursor = cursor

    def __len__(self):
        return len(self.list_)

    def __getitem__(self, slice):
        """
        Return the annotations from the given slice.
        """
        return self.list_[slice]

    def __iter__(self):
        return iter(self.list_)
    
    def cursor_at_time(self, time):
        """
        Set the internal cursor so that an annotation at the given
        time would be inserted in timestamp order.

        time -- the cursor is put between two annotations, so that the
        given time is between their timestamps (datetime.timedelta
        object).
        """
        self.cursor = bisect.bisect(
            [annotation.time for annotation in self.list_], time)

    def to_next_annotation(self):
        """
        Move the cursor forward by one annotation, and return the time of
        the annotation it passed.

        If there is no annotation after the cursor, nothing happens
        and NoAnnotation is raised.
        """

        if self.cursor == len(self):  # No next annotation
            raise NoAnnotation

        self.cursor += 1
        return self[self.cursor-1].time

    def to_prev_annotation(self):
        """
        Move the cursor backward by one annotation, and return the time of
        the annotation it passed.

        If there is no annotation before the cursor, nothing happens
        and NoAnnotation is raised.
        """

        if self.cursor == 0:  # No previous annotation
            raise NoAnnotation

        self.cursor -= 1
        return self[self.cursor].time
    
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
        """
        self.cursor -= 1        
        del self.list_[self.cursor]

    def to_builtins_fmt(self):
        """
        Return a version of the AnnotationList that only uses built-in
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
    def from_builtins_fmt(cls, annotation_kinds, annotations):
        """
        Reverse of to_builtins_fmt().

        annotation_kinds -- enumeration (enum.Enum) for interpreting
        the annotations. Its values must correspond to the annotation
        values stored in annotations.
        
        annotations -- annotation list in the form returned by
        to_builtins_fmt().
        """
        return cls(
            cursor=annotations["cursor"],
            list_=[
                TimestampedAnnotation.from_builtins_fmt(annotation_kinds,
                                                        annotation)
                for annotation in annotations["annotation_list"]
            ]
        )
        
def real_time_loop(stdscr, curr_event_ref, start_time, annotations,
                   annot_enum):
    """
    Run the main real-time annotation loop and return the annotation
    time at the time of exit.

    Displays and updates the given annotation list based on
    single characters entered by the user.

    stdscr -- curses.WindowObject for displaying information.

    curr_event_ref -- reference of the event (recording...)  being annotated.
    
    start_time -- starting annotation time (Time object).
    
    annotations -- AnnotationList to be updated.

    annot_enum -- enum.Enum enumeration with all the possible
    annotations. The names are the full names of the annotations,
    while the values are the corresponding characters.
    """

    # Events (get user key, transfer the next annotation to the list
    # of previous annotations) are handled by the following scheduler:
    scheduler = sched.scheduler(time.monotonic)

    # Counters for the event scheduling:
    start_counter = time.monotonic()

    # Starting the player is better done close to setting
    # start_counter, so that there is not large discrepancy between
    # the time in the player and this time measured by this
    # function:
    player_module.start()    
    
    def time_to_counter(time):
        """
        Return the scheduler counter corresponding to the given
        annotation timestamp.

        time -- time (datetime.timedelta, including Time).
        """
        return (time-start_time).total_seconds() + start_counter

    def counter_to_time(counter):
        """
        Return the annotation timestamp corresponding to the given
        scheduler counter.

        counter -- scheduler counter (in seconds).
        """
        return start_time + datetime.timedelta(seconds=counter-start_counter)

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
    help_start_line = term_lines - (len(annot_enum)+6)
    stdscr.hline(help_start_line, 0, curses.ACS_HLINE, term_cols)
    addstr_width(help_start_line+1, 0, "Commands:\n", curses.A_BOLD)
    stdscr.addstr("<Space>: return to shell\n")
    stdscr.addstr("<Del>: delete previous annotation\n")
    stdscr.addstr("<Left>, <Right>: navigate in annotations\n")
    for annotation in annot_enum:
        stdscr.addstr("{}: {}\n".format(annotation.value, annotation.name))
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

    # In order to cancel upcoming updates of the next annotation
    # (highlight and transfer to the list of previous events), the
    # corresponding events are stored in this list:
    cancelable_events = []
    def cancel_sched_events():
        """
        Cancel the scheduled events (except getting the next user key).

        The events canceled are in cancelable_events.
        """
        while cancelable_events:
            try:
                # Highlighting events are not tracked, so they
                # might have passed without this program knowing
                # it, which makes the following fail:
                scheduler.cancel(cancelable_events.pop())
            except ValueError:
                pass
    
    def display_annotations():
        """
        Display the list of previous annotations (erasing any text in the
        region of previous annotations), and the next annotation.

        Schedule the next annotation list update (with the next
        annotation going from the next annotation entry to the
        previous annotations list).
        """

        ####################
        # Previous annotations:
        
        ## If there is any annotation before the current time:
        if annotations.cursor:  # The slice below is cumbersome otherwise

            slice_end = annotations.cursor-1-prev_annot_height
            if slice_end < 0:
                slice_end = None  # For a Python slice

            for (line_idx, annotation) in enumerate(
                annotations[annotations.cursor-1 : slice_end :-1], 6):

                addstr_width(line_idx, 0, str(annotation))
                stdscr.clrtoeol()  # For existing annotations

        else:
            line_idx = 5  # Last "written" line

        # The rest of the lines are erased:
        for line_idx in range(line_idx+1, 5+prev_annot_height):
            stdscr.move(line_idx, 0)
            stdscr.clrtoeol()

        display_next_annotation()
        
    def display_next_annotation():
        """
        Display the next annotation and schedules the corresponding
        annotation list scrolling.

        The previous annotation list must be displayed already.
        """
        
        # Coordinate for the display (aligned with the running timer):
        x_display = 19
    
        # Display
        
        next_annotation = annotations.next_annotation()
        
        next_annotation_text = (str(next_annotation)
                                if next_annotation is not None else "<None>")
        
        addstr_width(2, x_display, next_annotation_text)
        stdscr.clrtoeol()

        if next_annotation is not None:

            nonlocal cancelable_events
            
            cancelable_events = [
                
                # Visual clue about upcoming annotation:
                scheduler.enterabs(
                    # The chosen delay must be larger than the time
                    # that it takes for the user to add a value to an
                    # annotation (otherwise, he would not always have
                    # enough time to target the previous annotation
                    # and change its value before it is replaced by
                    # the next annotation).
                    time_to_counter(next_annotation.time)-1, 0,
                    lambda: stdscr.chgat(
                    2, x_display,
                    len(next_annotation_text), curses.A_STANDOUT)),

                # The transfer of next_annotation will require the
                # list of previous annotations to be displayed:
                scheduler.enterabs(time_to_counter(next_annotation.time), 0,
                                   scroll_next_annotation)
                ]

    def scroll_next_annotation():
        """
        Move the current next annotation to the list of previous
        annotations, update the next annotation (if any) so that the
        displayed annotations remain consistent with the annotation
        cursor, and schedule the next scrolling (if necessary).

        A next annotation must be present (both on screen and in
        annotations, in a consistent way) when calling this function.
        """

        # Transfer on screen to the list of next annotations:
        #
        # This requires the previous annotations to be already displayed:
        stdscr.scroll(-1)
        addstr_width(6, 0, str(annotations.next_annotation()))
        
        # The cursor in the annotations list must be updated to
        # reflect the screen update:
        annotations.cursor += 1
    
        display_next_annotation()

        stdscr.refresh()  # Instant feedback
        
    display_annotations()
        
    ####################
    # User key handling:

    # Counter for the next getkey() (see below). This counter is
    # always such that the annotations.cursor corresponds to it
    # (with respect to the annotation times in annotations): the
    # two are always paired.
    next_getkey_counter = start_counter
    
    def getkey():
        """
        Get the user command (if any) and process it.

        Before doing this, refreshes the screen, and schedules
        the next key check.

        This event is always scheduled for the next_getkey_counter
        scheduler counter.
        """
        nonlocal next_getkey_counter

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
                annotation_kind = annot_enum(key)
            except ValueError:

                if key.isdigit():
                    if annotations.cursor:
                        (annotations.prev_annotation().set_value(int(key)))
                        # The screen must be updated so as to reflect
                        # the new value:
                        addstr_width(
                            6, 0,  str(annotations.prev_annotation()))
                        stdscr.clrtoeol()
                        stdscr.refresh()  # Instant feedback
                    else:  # No previous annotation
                        curses.beep()
                elif key == "\x7f":
                    # ASCII delete: delete the previous annotation
                    if annotations.cursor:

                        annotations.delete_prev()
                        # Corresponding screen update:
                        stdscr.scroll()
                        # The last line in the list of previous
                        # annotations might have to be updated:
                        index_new_prev_annot = (
                            annotations.cursor-prev_annot_height)
                        if index_new_prev_annot >= 0:
                            addstr_width(
                                5+prev_annot_height, 0,
                                str(annotations[index_new_prev_annot]))
                        # Instant feedback:
                        stdscr.refresh()

                    else:
                        curses.beep()  # Error: no previous annotation
                elif key in {"KEY_RIGHT", "KEY_LEFT"}:
                    
                    # Screen and cursor update:
                    if key == "KEY_RIGHT":
                        next_annotation = annotations.next_annotation()
                        if next_annotation is None:
                            curses.beep()
                        else:
                            scroll_next_annotation()
                            # !!!!!! update with new
                    
                    try:
                        new_time = (
                            annotations.to_next_annotation
                            if key == "KEY_RIGHT"
                            else annotations.to_prev_annotation)()
                        
                    except NoAnnotation:
                        curses.beep()  # No annotation to go to
                    else:

                        if key == "KEY_LEFT":
                            # In order to allow the user to move
                            # beyond just the previous annotation,
                            # there is a small time window after each
                            # annotation during which going backwards
                            # moves *two* annotations back. In effect,
                            # this skips the previous annotation and
                            # goes back to the one before:

                            if (counter_to_time(next_getkey_counter)
                                -new_time) < REPEAT_KEY_TIME:
                                
                                try:
                                    new_time = annotations.to_prev_annotation()
                                except NoAnnotation:
                                    pass

                        # The relationship between the annotation
                        # timer and the scheduler timer must be
                        # updated:
                        nonlocal start_time, start_counter
                        start_time = new_time
                        start_counter = next_getkey_counter
                        player_module.set_time(*new_time.to_HMS())

                        # Screen update of the existing annotations:

                        # Any queued event must be canceled, as they
                        # are obsolete, since they are tied to the
                        # time next_getkey_counter (instead of
                        # new_time):
                        cancel_sched_events()
                        #
                        # !!!! This is not efficient: for forward, a
                        # simple scroll down of the next annotation
                        # would do. For backward movement
                        display_annotations()

                elif key != " ":  # Space is a valid key
                    curses.beep()  # Unknown key

            else:  # A user annotation key was given:
                
                annotations.insert(TimestampedAnnotation(
                    annotation_time, annotation_kind))
                # Display update:
                stdscr.scroll(-1)
                addstr_width(6, 0, str(annotations.prev_annotation()))
                stdscr.refresh()  # Instant feedback

        # Looping through the scheduling of the next key check:
        if key == " ":

            # Stopping the player is best done as soon as possible, so
            # as to keep the synchronization between self.time and the
            # player time as well as possible, in case
            # player_module.set_time() is a no-op but
            # player_module.stop() works:
            player_module.stop()

            # No new scheduling of a possible user key reading.

            # Existing scheduled events (highlighting and transfer of
            # the next annotation to the previous annotations) must be
            # canceled (otherwise the scheduler will not quit because
            # it has events waiting in the queue):
            cancel_sched_events()
            
        else:
            next_getkey_counter += 0.1  # Seconds
            # Using absolute counters makes the counter more
            # regular, in particular when some longer
            # tasks take time (compared to using a
            # relative waiting time at each iteration of
            # the loop).
            scheduler.enterabs(next_getkey_counter, 0, getkey)

    scheduler.enterabs(next_getkey_counter, 0, getkey)
    scheduler.run()

    # The pause key was entered at the last next_getkey_counter, so
    # this is the time used for updating the event timer:
    getkey_time = counter_to_time(next_getkey_counter)
    player_module.set_time(*getkey_time.to_HMS())  # Explicit synchronization
    return getkey_time
    
class AnnotateShell(cmd.Cmd):
    """
    Shell for launching a real-time annotation recording loop.
    """
    intro = "Type ? (or help) for help. Use <Tab> for automatic completion."
    prompt = ">>> "

    def __init__(self, annotations_path):
        """
        annotations_path -- pathlib.Path to the file with the annotations.
        """

        super().__init__()

        self.annotations_path = annotations_path
        
        # Current event to be annotated:
        self.curr_event_ref = None
        
        # Reading of the existing annotations:
        if annotations_path.exists():

            with annotations_path.open("r") as annotations_file:
                file_contents = json.load(annotations_file)

            # Extraction of the file contents:
            #
            # The key assignments (represented as an enum.Enum)
            # might not be defined yet:

            self.annot_enum = (
                enum.Enum("AnnotationKind", file_contents["key_assignments"])
                if file_contents["key_assignments"] is not None
                else None)

            self.all_annotations = collections.defaultdict(
                AnnotationList,
                {
                 # self.annot_enum is guaranteed by this program to
                 # not be None if there is any annotation: the user is
                 # forced to load key assignments before any
                 # annotation can be made:
                 event_ref:
                 AnnotationList.from_builtins_fmt(self.annot_enum, annotations)
                 for (event_ref, annotations)
                 in file_contents["annotations"].items()})

            self.do_list_events()

        else:  # A new file must to be created
            self.annot_enum = None
            self.all_annotations = collections.defaultdict(AnnotationList)
            self.do_save()
            
        # Automatic (optional) saving of the annotations, both for
        # regular quitting and for exceptions:
        def save_if_needed():
            """
            Save the updated annotations if wanted.
            """
            print()
            if input("Do you want to save the annotations and key"
                     " assignments (y/n)? [y] ") != "n":
                self.do_save()
        atexit.register(save_if_needed)

    @property
    def time(self):
        """
        Time of the annotation timer.
        """
        return self._time

    @time.setter
    def time(self, time):
        """
        Set both the annotation timer and the player time to the given
        time.

        time -- Time object.
        """
        self._time = time
        player_module.set_time(*time.to_HMS())
    
    def emptyline(self):
        pass  # No repetition of the last command
    
    def do_save(self, arg=None):
        """
        Save the current annotations to file after making a copy of any
        previous version.

        If no previous version was available, a new file is created.
        """

        if self.annotations_path.exists():
            # The old annotations are backed up:
            backup_path = str(self.annotations_path)+".bak"
            shutil.copyfile(str(self.annotations_path), backup_path)
            print("Previous annotations copied to {}.".format(backup_path))
        else:
            # A new file must be created:
            print("Creating a new annotation file...")
            
        # Dump of the new annotations database:
        with self.annotations_path.open("w") as annotations_file:

            # Serializable version of the possible annotations:
            annot_enum_for_file = (
                None if self.annot_enum is None
                # The order of the enumerations is preserved:                
                else [(annot.name, annot.value) for annot in self.annot_enum]
            )

            # !! Another architecture would consist in only keep in
            # memory and converting (upon writing and reading) the
            # annotations for those events that the user touched. This
            # would save memory and processing time, at the cost of
            # slightly more complicated code (because the in-memory
            # data would basically be an updated cache that has
            # priority over the file data: handling this priority is
            # not as straightforward as the current "read/write all
            # events" method.
            all_annotations_for_file = {
                event_ref: annotation_list.to_builtins_fmt()
                for (event_ref, annotation_list)
                in self.all_annotations.items()
            }

            json.dump({"annotations": all_annotations_for_file,
                       "key_assignments": annot_enum_for_file},
                      annotations_file, indent=2)
            
        print("Annotations (and key assignments) saved to {}."
              .format(self.annotations_path))
    
    def do_exit(self, arg=None):
        """
        Exit this program and optionally save the annotations.
        """
        # The handling of the optional, final saving of the updated
        # annotations is handled by an atexit handler:
        return True  # Quit

    def do_EOF(self, arg):
        return self.do_exit(arg)
    do_EOF.__doc__ = do_exit.__doc__

    def do_set_time(self, time):
        """
        Set the current annotation timer to the given time.

        If a player is used, this time should typically be the play
        head location.

        time -- time in S, M:S or H:M:S format.
        """
        try:
            # No need to have the program crash and exit for a small error:
            time_parts = list(map(float, time.split(":", 2)))
        except ValueError:
            print("Incorrect time format. Use M:S or H:M:S.")
        else:
            self.time = Time(**dict(zip(["seconds", "minutes", "hours"],
                                        time_parts[::-1])))

            print("Annotation timer set to {}.".format(self.time))

    def do_load_keys(self, file_path):
        """
        Load key assignments from the given file. They are saved with
        the annotations. This can be used for modifying or updating
        the annotations associated with a file.

        The file format is as follows:

        # Musical annotations
        
        s    start (between pieces, before the beginning)
        e    end (0 = could be an end if needed)
        ...

        The first letter is a character (case sensitive). Typing this
        character will insert the annotation described afterwards (free
        text).

        The key can be followed by any number of spaces, which are
        followed by a text describing the meaning of the annotation
        (and optionally of any numeric modifier).

        Empty lines and lines starting by # are ignored.

        WARNING

        Annotations are represented by their character only. Any
        change in the key assignments of an annotation file must be
        done with this in mind.
        
        KEY ASSIGNMENT CHANGES

        The description text can be updated (usually in a way
        consistent with the meaning of event annotations that use its
        key).
        
        New keys can be added.
        
        If a key which is used in events disappears, the user is
        prompted for the replacement key.
        """
        
        # Common error: no file name given:
        if not file_path:
            print("Error: please provide a file path.")
            return

        # It is convenient to keep the annotations in the same order
        # as in the file:
        key_assignments = collections.OrderedDict()

        try:
            keys_file = open(file_path)
        except IOError as err:
            print("Error: cannot open '{}': {}".format(file_path, err))
            return
        
        with keys_file:
            for (line_num, line) in enumerate(keys_file, 1):
                
                line = line.rstrip()

                # Empty lines and comments are skipped:
                if not line or line.startswith("#"):
                    continue
                
                try:
                    key, text = line.split(None, 1)
                except ValueError:
                    print("Error: syntax error in line {}:\n{}".format(
                        line_num, line))
                    return

                # Sanity checks:
                
                if len(key) != 1:
                    print("Error: keys must be single characters. Error"
                          " in line {} with key '{}'."
                          .format(line_num, key))
                    return
                
                if key.isdigit():
                    print("Error: digits are reserved keys.")
                    return
                
                # The other reserved keys are space and delete,
                # but space cannot be entered in the file, and
                # delete is cumbersome to enter, so this case is
                # not checked.
                key_assignments[text] = key

        print("Key assignments loaded from file {}.".format(file_path))
                    
        try:
            new_annot_enum = enum.unique(
                enum.Enum("AnnotationKind", key_assignments))
        except ValueError as err:  # Non-unique keyboard keys
            print("Error: all keyboard keys should be different.")
            return

        # The old key assignments are saved, for a rollback in case of
        # problem:
        old_annot_num = self.annot_enum
        
        self.annot_enum = new_annot_enum
        self.do_list_keys()

        # Existing annotations (self.all_annotations) use the old
        # annotation kinds (old_annot_enum). These annotations contain
        # text that may have been updated in the new key assignment
        # file, so they should be updated. They might also contain
        # annotation keys that have disappeared from the key
        # assignments (through renaming, etc.): ignoring this would
        # prevent the annotation file from being re-opened, as there
        # would be no way to interpret them with the new
        # annotations.
        #
        # A solution to both of these issues consists in first
        # defining the conversions between the old and new
        # annotations, automatically through a common key if possible,
        # or with the input of the user if a key has disappeared (who
        # either indicates the new annotation that replaces the old
        # one, or if this is not possible, cancels the new key
        # assignments).

        # The enumeration constant conversions are first determined:
        # this makes it easier to let the user cancel the new key
        # assignments, in case they are incorrect (for example in the
        # case where one of the old annotations does not correspond to
        # any new one), as this is detected early.

        old_annotations = set()  # Set with all *used* annotations
        for (event_ref, annotations) in self.all_annotations.items():
            for timed_annotation in annotations:
                old_annotations.add(timed_annotation.annotation)

        # Calculation of the mapping "conversions" from old to new
        # enumerated constants:
        conversions = {}

        for old_annotation in old_annotations:

            # First key tried for finding the new annotation
            # corresponding to old_annotation:
            key = old_annotation.value
            
            while True:

                try:
                    # Do we have a new annotation with the same key?
                    new_annotation = new_annot_enum(key)
                except ValueError:

                    print("Problem: key {} not found in new key assignments."
                          .format(key))

                    key = input(
                        "New key that {} should be replaced with"
                        " (or Enter, for reverting to the previous"
                        " key assignments): ".format(key))

                    if not key:
                        self.annot_enum = old_annot_num
                        print("New key assignments canceled.")
                        self.do_list_keys()
                        return

                else:
                    break  # Equivalent new_annotation determined

            conversions[old_annotation] = new_annotation

        # Now that all the necessary annotation constant conversions
        # are defined, they can be applied:
        for (event_ref, annotations) in self.all_annotations.items():
            for timed_annotation in annotations:
                timed_annotation.annotation = conversions[
                    timed_annotation.annotation]
        
    def complete_load_keys(self, text, line, begidx, endidx):
        """
        Complete the text with paths from the current directory.
        """

        # When the line ends with "/", "text" appears to be empty.
        if line.endswith("/"):
            # Directory completion
            directory = pathlib.Path(line.split(None, 1)[1])
            ## print("DIRECTORY", directory)
            ## print([
            ##     # The completions must only include file names
            ##     # *without the prefix in "line" (otherwise the
            ##     # beginning of the path is repeated in the command
            ##     # line):
            ##     str(path.relative_to(directory))
            ##     for path in directory.glob("*")
            ##     ])
            
            return [
                # The completions must only include file names
                # *without the prefix in "line" (otherwise the
                # beginning of the path is repeated in the command
                # line):
                str(path.relative_to(directory))
                for path in directory.glob("*")
                ]
    
        else:
            # Direct expansion:


            # Special characters like "*" at the beginning of the
            # string entered by the user are not included in "text" by
            # the cmd modul, so they are explicitly included by
            # calculating "start":
            #
            # Part before the text, without the command:
            try:
                start = line[:begidx].split(None, 1)[1]
            except IndexError:
                # Case of a completion from an empty string:
                start = ""

            # The escape() takes care of characters that are
            # interpreted by glob(), like *:                
            glob_expr = "{}*".format(glob.escape(start+text))
            ## print("GLOB expr", glob_expr)
                
            return [
                # Only the part after begidx must be returned:
                glob_result[len(start):]
                for glob_result in glob.glob(glob_expr)
                ]
        
    def do_annotate(self, arg):
        """
        Immediately start recording annotations for the current
        event reference. This event must first be set with
        select_event.

        The annotation file must also contain annotation key
        definitions. This typically has to be done once after creating
        the file, with the command load_keys.
        """

        if self.annot_enum is None:
            print("Error: please load key assignments first (load_keys"
                  " command).")
            return
        
        if self.curr_event_ref is None:
            print("Error: please select an event to be annotated",
                  "with select_event.")
            return

        try:
            
            # The real-time loop displays information in a curses window:
            self.time = curses.wrapper(
                real_time_loop, self.curr_event_ref, self.time,
                self.all_annotations[self.curr_event_ref],
                self.annot_enum)
            
        except TerminalNotHighEnough:
            print("Error: the terminal is not high enough.")
        else:
            print("Current timestamp: {}.".format(self.time))

    def do_list_events(self, arg=None):
        """
        List annotated events.
        """

        if self.all_annotations:
            print("Annotated events (sorted alphabetically):")
            for event_ref in sorted(self.all_annotations):
                print("- {}".format(event_ref))
        else:
            print("No annotated event found.")

    def do_list_keys(self, arg=None):
        """
        List the key assignments for annotations (loaded by load_keys and
        saved in the annotation file).
        """
        print("Annotation keys:")
        for annotation in self.annot_enum:
            print("{}: {}".format(annotation.value, annotation.name))
        
    def do_select_event(self, event_ref):
        """
        Set the given event reference as the current event.

        If the event does not exist yet, it is created.
        
        The current list of references can be obtained with
        list_events.

        Annotations are attached to this event.
        """
        self.curr_event_ref = event_ref

        # Annotation list for the current event:
        annotations = self.all_annotations[event_ref]
        print("Current event set to {}.".format(event_ref))
        print("{} annotations found.".format(len(annotations)))

        prev_annotation = annotations.prev_annotation()
        
        # The time of the previous annotation before the cursor is
        # "just" before when the user last stopped:
        self.time = (prev_annotation.time if prev_annotation is not None
                     else Time())
        print("Back to previous annotation. Annotation timer set to {}."
              .format(self.time))
        
    def complete_select_event(self, text, line, begidx, endidx):
        """
        Complete event references with the known references.
        """
        return [event_ref for event_ref in sorted(self.all_annotations)
                if event_ref.startswith(text)]

    def do_del_event(self, event_ref):
        """
        Delete the given event.
        """
        try:
            del self.all_annotations[event_ref]
        except KeyError:
            print('Error: unknown event "{}".'.format(event_ref))
            
    complete_del_event = complete_select_event
    
    def do_rename_event(self, arg):
        """
        Rename the given event.

        Syntax:
        rename_event current_name -> new_name
        """

        try:
            current_name, new_name = map(
                # arg seems to be stripped already, but this is not
                # documented, so this is done manually here:
                lambda name: name.strip(), arg.split("->"))
        except ValueError:
            print("Syntax error. See help rename_event.")
            return

        # Existing events must not be clobbered:
        if new_name in self.all_annotations:
            print('Problem: event "{}" exists. You can delete it if needed.'
                  " Renaming aborted.".format(new_name))
            return

        try:
            # Renaming:
            self.all_annotations[new_name] = self.all_annotations.pop(
                current_name)
        except KeyError:
            print('Error: event "{}" not found.'.format(current_name))
            return
        
    complete_rename_event = complete_select_event
        
if __name__ == "__main__":
    
    import argparse
    import collections
    
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--player", metavar="python_module", action="store",
        help=("Name of Python module that controls some real-time player"
              " (music player, etc.)."
              " The module must be in the Python module path (working"
              " directory, directory of this program, etc.)"
              " The module must provide a start() and"
              " a stop() function (that take no argument), and a"
              " function set_time(hours, minutes, seconds)."
              " start() is called when the annotation process starts,"
              " stop() when it is stopped."
              " set_time() is called when the user sets the time of the"
              " annotation timer."
              " Annotations times can thus be"
              " synchronized with the elapsed time in a piece of music, etc."))
    
    parser.add_argument(
        "annotation_file",
        help=("Path to the annotation file (it will be created if it does not"
              " yet exist)"))

    args = parser.parse_args()

    player_functions = ["start", "stop", "set_time"]
    if args.player:
        player_module = __import__(args.player, fromlist=player_functions)
    else:  # Default player (which does nothing):
        player_module = sys.modules[__name__]  # This module
        for func_name in player_functions:
            setattr(player_module, func_name, lambda *args: None)
        
    AnnotateShell(pathlib.Path(args.annotation_file)).cmdloop()
