#!/usr/bin/env python3.4

"""
Annotations tagged with a timestamp.

Ad hoc annotations for judging a long string of recordings.
"""

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

import yaml

# File that contains the annotations. It contains a mapping from recording
# references to their annotations.
ANNOTATIONS_PATH = pathlib.Path("annotations.yaml")

# Mapping from keyboard keys to the corresponding enumeration name
# (which must be a valid Python attribute name):
#
# WARNING: Entries can only be added (not removed, because this would
# make previous annotation files illegible), and they must be added at
# the end (because the files data relies on the order).
#
# WARNING 2: Some keys are reserved for the control of the real-time
# interface: space, delete, and digits.
annotation_keys = collections.OrderedDict([
    ("s", "start"),
    ("e", "end"),
    ("i", "inspired"),
    ("u", "uninspired"),
    ("g", "glitch")
    ])
    
Annotation = enum.Enum("Annotation", list(annotation_keys.values()))

class Time(datetime.timedelta):
    """
    Timestamp: time since the beginning of a recording.
    """
    
    # ! A datetime.timedelta is used instead of a datetime.time
    # because the internal timer of this program must be added to the
    # current recording timestamp so as to update it. This cannot be
    # done with datetime.time objects (which cannot be added to a
    # timedelta).
    def __str__(self):
        """
        Same representation as a datetime.timedelta, but without
        fractional seconds.
        """
        return "{}.{:.0f}".format(
            super().__str__().split(".", 1)[0], self.microseconds/1e5)

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
    - annotation (Annotation)

    An value can be added to the annotation. It is stored in the
    optional 'value' attribute. This is typically used for indicating
    an intensity (such as a small glitch, or a very uninspired part).
    """
    def __init__(self, time, annotation):
        """
        Annotation represented by the given keyboard key.

        time -- timestamp for the annotation, as a datetime.timedelta.
        
        annotation -- Annotation to be stored.
        """
        self.time = time
        self.annotation = annotation
    
    def set_value(self, value):
        """
        Set the annotation's value.
        """
        self.value = value

    def __str__(self):
        
        result = "{} {}".format(self.time, self.annotation.name)
        
        if hasattr(self, "value"):
            result += " (value {})".format(self.value)
            
        return result
    
class NoAnnotation(Exception):
    """
    Raise when a requested annotation cannot be found.
    """
    
class AnnotationList:
    """
    List of annotations sorted by timestamp.

    Main attributes:
    - annotations: list of Annotations, sorted by increasing timestamp.
    - cursor: index between annotations (0 = before the first annotation).
    """
    def __init__(self):
        self.annotations = []
        self.cursor = 0

    def __len__(self):
        return len(self.annotations)

    def move_cursor(self, time):
        """
        Set the internal cursor so that an annotation at the given
        time would be inserted in timestamp order.

        time -- the cursor is put between two annotations, so that the
        given time is between their timestamps (datetime.timedelta
        object).
        """
        self.cursor = bisect.bisect(
            [annotation.time for annotation in self.annotations], time)

    def __getitem__(self, slice):
        """
        Return the annotations from the given slice.
        """
        return self.annotations[slice]
    
    def next_annotation(self):
        """
        Return the first annotation after the cursor, or None if there
        is none.
        """
        try:
            return self[self.cursor]
        except IndexError:
            return None

    def insert(self, annotation):
        """
        Insert the given annotation at the cursor location and moves
        it to after the inserted annotation (so that a next insert()
        on the next annotation in time puts it in the right place in
        the list).

        The cursor must be located so that the insertion is done in
        timestamp order. Using move_cursor(annotation.time) does this
        (but this call is not required, as the cursor can be set by
        other means too, including outside of this class).
        """
        self.annotations.insert(self.cursor, annotation)
        self.cursor += 1

    def delete_last(self):
        """
        Delete the annotation just before the cursor and update the
        cursor (which does not move compared to its following
        annotation).
        """
        self.cursor -= 1        
        del self.annotations[self.cursor]
    
def real_time_loop(stdscr, recording_ref, start_time, annotation_list):
    """
    Run the main real-time annotation loop and return the time in the
    recording, when exiting.

    Displays and updates the given annotation list based on
    user command keys.

    stdscr -- curses.WindowObject for displaying information.

    recording_ref -- reference of the recording being annotated.
    
    start_time -- time in the recording when play starts (Time object).
    
    annotation_list -- AnnotationList to be updated.
    """

    # Events (get user key, transfer the next annotation to the list
    # of previous annotations) are handled by the following scheduler:
    scheduler = sched.scheduler(time.monotonic)

    # Counters for the event scheduling:
    start_counter = time.monotonic()

    # !!!!! Send *play* command to Logic Pro. This is better done
    # close to setting start_counter, so that there is not large
    # discrepancy between the time in the recording and this time
    # measured by this function.
    
    def time_to_counter(time):
        """
        Return the scheduler counter corresponding to the given
        recording time.

        time -- recording time (datetime.timedelta, including Time).
        """
        return (time-start_time).total_seconds() + start_counter

    def counter_to_time(counter):
        """
        Return the recording time corresponding to the given scheduler
        counter.

        counter -- scheduler counter (in seconds).
        """
        return start_time + datetime.timedelta(seconds=counter-start_counter)


    # Basic settings for the terminal:
    
    ## The terminal's default is better than curses's default:
    curses.use_default_colors()
    ## For looping without waiting for the user:
    stdscr.nodelay(True)
    ## No need to see any cursor:
    curses.curs_set(0)
    ## No need to have a cursor at the correct position:
    stdscr.leaveok(True)
    ## Scrolling region (for previous annotations):
    stdscr.scrollok(True)
    ## term_lines-1)  #!!!!! Set to full window, minus command list
    num_prev_annot = 4  # Maximum number of previous annotations in window
    stdscr.setscrreg(6, 5+num_prev_annot)

    # Initializations:
    
    ## Terminal size:
    (term_lines, term_cols) = stdscr.getmaxyx()
    
    ## Annotations cursor:
    annotation_list.move_cursor(start_time)
    
    # Static information:
    stdscr.clear()
    
    stdscr.addstr(0, 0, "Recording:", curses.A_BOLD)
    stdscr.addstr(0, 11, recording_ref)
    
    stdscr.hline(1, 0, curses.ACS_HLINE, term_cols)

    stdscr.addstr(2, 0, "Next annotation:", curses.A_BOLD)
        
    stdscr.addstr(3, 0, "Time in recording:", curses.A_BOLD)

    stdscr.hline(4, 0, curses.ACS_HLINE, term_cols)
    
    stdscr.addstr(5, 0, "Previous annotations:", curses.A_BOLD)
    
    # If there is any annotation before the current time:
    if annotation_list.cursor:  # The slice below is cumbersome otherwise
        
        slice_end = annotation_list.cursor-1-num_prev_annot
        if slice_end < 0:
            slice_end = None  # For a Python slice

        for (line_idx, annotation) in enumerate(
            annotation_list.annotations[
                annotation_list.cursor-1 : slice_end :-1],
            6):

            stdscr.addstr(line_idx, 0, str(annotation))

    # Now that the previous annotations are listed, the next
    # annotation can be printed and its updates scheduled:

    # In order to cancel upcoming updates of the next annotation
    # (highlight and transfer to the list of previous events), the
    # corresponding events are stored in this list:
    next_annotation_upcoming_events = []

    def display_next_annotation():
        """
        Update the display of the next annotation with the current
        next annotation in annotation_list and schedule its screen
        update (going from the next annotation entry to the previous
        annotations list).

        The previous annotations must be already displayed (otherwise
        the scheduled update for the next annotation might break the
        display).
        """
        # Coordinate for the display (aligned with the running timer):
        x_display = 18
    
        # Display
        next_annotation = annotation_list.next_annotation()
        next_annotation_text = (str(next_annotation)
                                if next_annotation is not None else "<None>")
        stdscr.addstr(2, x_display, next_annotation_text)
        stdscr.clrtoeol()

        if next_annotation is not None:

            nonlocal next_annotation_upcoming_events
            
            next_annotation_upcoming_events = [
                
                # Visual clue about upcoming annotation:
                scheduler.enterabs(
                    time_to_counter(next_annotation.time)-1, 0,
                    lambda: stdscr.chgat(
                    2, x_display,
                    len(next_annotation_text), curses.A_STANDOUT)),

                scheduler.enterabs(time_to_counter(next_annotation.time), 0,
                                   transfer_next_annotation)
                ]

    def transfer_next_annotation():
        """
        Move the current next annotation (which does exist) to the
        list of previous annotations, update the next annotation (if
        any), and schedule the next transfer (if necessary).
        """

        # Transfer on screen to the list of next annotations:
        #
        # This requires the previous annotations to be already displayed:
        stdscr.scroll(-1)
        stdscr.addstr(6, 0, str(annotation_list.next_annotation()))
        stdscr.refresh()  # Instant feedback
        
        # The cursor in the annotations list must be updated to
        # reflect the screen update:
        annotation_list.cursor += 1
    
        display_next_annotation()

    display_next_annotation()
        
    # General information (mini-help):
    # !!!!!! Print commands at the bottom of the screen and keep there

    # Counter for the next getkey() (see below). This counter is
    # always such that the annotation_list.cursor corresponds to it
    # (with respect to the annotation times in annotation_list): the
    # two are always paired.
    next_getkey_counter = start_counter
    
    def getkey():
        """
        Get the user key command (if any) and process it.

        Before doing this, refreshes the screen, and schedules
        the next command key check.

        This event is always scheduled for the next_getkey_counter
        time.
        """
        nonlocal next_getkey_counter

        # Current time in the recording:
        recording_time = counter_to_time(next_getkey_counter)
    
        stdscr.addstr(3, 19, str(recording_time))
        stdscr.clrtoeol()  # The time can have a varying size

        try:
            key = stdscr.getkey()
        except curses.error:
            key = None  # No key pressed
        else:

            if key in annotation_keys:  # Annotation
                annotation = TimestampedAnnotation(
                    recording_time, Annotation[annotation_keys[key]])
                annotation_list.insert(annotation)
                # Display update:
                stdscr.scroll(-1)
                stdscr.addstr(6, 0, str(annotation))
                stdscr.refresh()
            elif key.isdigit():
                if annotation_list.cursor:
                    # !!!!!! Handle value
                    pass
                else:  # No previous annotation
                    curses.beep()
            elif key == "\x7f":  # ASCII delete: delete the previous annotation
                if annotation_list.cursor:
                    
                    annotation_list.delete_last()
                    # Corresponding screen update:
                    stdscr.scroll()
                    # The last line in the list of previous
                    # annotations might have to be updated:
                    index_new_prev_annot = (
                        annotation_list.cursor-num_prev_annot)
                    if index_new_prev_annot >= 0:
                        stdscr.addstr(
                            5+num_prev_annot, 0,
                            str(annotation_list.annotations
                                [index_new_prev_annot]))
                    
                else:
                    curses.beep()  # Error: no previous annotation

        
        if key == " ":
            # No new scheduling of a possible user key reading.

            # Existing scheduled events (highlighting and transfer of
            # the next annotation to the previous annotations) must be
            # canceled (otherwise the scheduler will not quit because
            # it has events waiting in the queue):

            for event in next_annotation_upcoming_events:
                try:
                    # Highlighting events are not tracked, so they
                    # might have passed without this program knowing
                    # it, which makes the following fail:
                    scheduler.cancel(event)
                except ValueError:
                    pass
            
            # !!!!! Stop play
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

    # !!! Resize the terminal during the loop and see the effect

    # The pause key was entered at the last next_getkey_counter:
    return counter_to_time(next_getkey_counter)
    
class AnnotateShell(cmd.Cmd):
    """
    Shell for launching a real-time recording annotation loop.
    """
    intro = "Welcome to the annotation shell."
    prompt = "> "

    def __init__(self, recording_ref):
        """
        recording_ref -- reference of the recording to be annotated (in
        file ANNOTATIONS_PATH).
        """

        super().__init__()
    
        print("Recording to be annotated: {}.".format(args.recording_ref))
        self.recording_ref = recording_ref
        
        # Reading of the existing annotations:
        with ANNOTATIONS_PATH.open("r") as annotations_file:
            annotations = yaml.load(annotations_file)[recording_ref]
        print("{} annotations found for {}.".format(
            len(annotations), recording_ref))
        self.annotations = annotations

        try:
            self.time = annotations.annotations[-1].time
        except IndexError:
            self.time = Time()  # Start
        print("Time in recording set to last annotation timestamp: {}."
              .format(self.time))

        # Automatic (optional) saving of the annotations, both for
        # regular quitting and for exceptions:
        def save_if_needed():
            """
            Save the updated annotations if wanted.
            """
            print()
            if input("Do you want to save the annotations (y/n)? [y] ") != "n":
                self.do_save()
        atexit.register(save_if_needed)

    def emptyline(self):
        pass  # No repetition of the last command
    
    def do_save(self, arg=None):
        """
        Save the current annotations to file.
        """

        # The old annotations are backed up:
        backup_path = str(ANNOTATIONS_PATH)+".bak"
        shutil.copyfile(str(ANNOTATIONS_PATH), backup_path)
        print("Previous annotations copied to {}.".format(backup_path))

        # Update of the annotations database:
        with ANNOTATIONS_PATH.open("r") as annotations_file:
            all_annotations = yaml.load(annotations_file)
        all_annotations[self.recording_ref] = self.annotations

        # Dump of the new annotations database:
        with ANNOTATIONS_PATH.open("w") as annotations_file:
            yaml.dump(all_annotations, annotations_file)
        print("Updated annotations for {} saved in {}.".format(
            self.recording_ref, ANNOTATIONS_PATH))
    
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
        Set the current time in the recording to the given time.

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
            
            # !!! Ideally, the time would be set automatically in
            # Logic Pro as well, but I'm not sure how to do this.
        
            print("Time in recording set to {}.".format(self.time))

    def do_play(self, arg):
        """
        Start playing the recording in Logic Pro, and record annotations.
        """
        # The real-time loop displays information in a curses window:
        self.time = curses.wrapper(
            real_time_loop, self.recording_ref, self.time, self.annotations)
        
        print("New recording timestamp: {}.".format(self.time))
        
def annotate_shell(args):
    """
    Launch a shell for annotating a recording.

    args -- command-line arguments of the annotate command.
    """
    shell = AnnotateShell(args.recording_ref)
    shell.cmdloop()

def list_recordings(args):
    """
    List recordings that are already annotated.

    args -- command-line arguments of the list command (ignored).
    """
    with ANNOTATIONS_PATH.open("r") as annotations_file:
        annotations = yaml.load(annotations_file)
    if annotations:
        print("Annotated recordings (by sorted reference):")
        for recording_ref in sorted(annotations):
            print("- {}".format(recording_ref))
    else:
        print("No annotation found.")

if __name__ == "__main__":
    
    import argparse
    import collections
    
    parser = argparse.ArgumentParser(
        description="Timestamped musical annotations.")

    subparsers = parser.add_subparsers()

    parser_annotate = subparsers.add_parser(
        "annotate", help="annotate recording")
    parser_annotate.add_argument(
        "recording_ref",
        help="Reference to the recording to be annotated")
    parser_annotate.set_defaults(func=annotate_shell)
    
    parser_list = subparsers.add_parser(
        "list", help="list references of annotated recordings")
    parser_list.set_defaults(func=list_recordings)
    
    args = parser.parse_args()

    ####################

    # The annotations file is created, if it does not already exist:
    print("Annotations file: {}.".format(ANNOTATIONS_PATH))
    
    # The annotation file is created if it does not exist:
    if not ANNOTATIONS_PATH.exists():
        # An empty annotation database is created:
        with ANNOTATIONS_PATH.open("w") as annotations_file:
            # Annotations for unknown recordings are empty lists by default:
            yaml.dump(collections.defaultdict(AnnotationList),
                      annotations_file)

    try:
        # Execution of the function set for the chosen command:
        args.func(args)
    except AttributeError:
        # No command given
        parser.error("Please provide a command.")



