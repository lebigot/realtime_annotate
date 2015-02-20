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

import yaml

# File that contains the annotations. It contains a mapping from recording
# references to their annotations.
ANNOTATIONS_PATH = pathlib.Path("annotations.yaml")

# !!!!!!!!! Ideally, I would check my listening notes for my CD and
# also for 2014-6-21, to know what kind of annotations I make. For
# instance, maybe adding some level indication (optional) would be
# good, like inspired 2 (meaning "a lot", or something), or "glitch 1"
# (small) or "glitch 2" (big). OR MAYBE simply adding "adjectives"
# would be enough: small and big (big glitch, very much uninspired,
# etc.).

# Mapping from keyboard keys to the corresponding enumeration name
# (which must be a valid Python attribute name):
annotation_keys = {
    "s": "start",
    "e": "end",
    "i": "inspired",
    "u": "uninspired",
    "g": "glitch"
    }
    
Annotation = enum.Enum("Annotation", list(annotation_keys.values()))

#!!!!!!!! There is a problem, here: there is no room for adding a
#level for inspired/etc. How to cleanly handle these?

class TimeStampedAnnotation:
    """
    Annotation made at a specific time.

    Main attributes:
    - time (datetime.time)
    - annotation (Annotation)

    An value can be added to the annotation. It is stored in the
    optional 'value' attribute. This is typically used for indicating
    an intensity (such as a small glitch, or a very uninspired part).
    """
    def __init__(self, time, key):
        """
        Annotation represented by the given keyboard key.

        time -- timestamp for the annotation, as a datetime.time
        object.
        
        key -- keyboard key. Must be present in annotation_keys.
        """
        self.time = time
        self.annotation = Annotation[annotation_keys[key]]

    def set_value(self, value):
        """
        Set the annotation's value.
        """
        self.value = value

class AnnotationList:
    """
    List of annotations sorted by timestamp.

    Main attributes:
    - annotations: list of annotations, sorted by increasing timestamp.
    """
    def __init__(self):
        self.annotations = []

    def __len__(self):
        return len(self.annotations)
    # !!!!! Will be populated as the needs arise

class AnnotateShell(cmd.Cmd):
    """
    Shell for launching a real-time recording annotation loop.
    """
    intro = "Welcome to the annotation shell. Type help or ? to list commands."
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
            self.time = datetime.time()  # Start
        print("Time in recording set to {}.".format(self.time))

        # Automatic (optional) saving of the annotations, both for
        # regular quitting and for exceptions:
        def save_if_needed():
            """
            Save the updated annotations if wanted.
            """
            if input("Do you want to save the annotations (y/n)? [y] ") != "n":
                self.do_save()

        atexit.register(save_if_needed)
        
    def do_save(self, arg=None):
        """
        Save the current the annotations to file.
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

        time -- time in M:S or H:M:S format.
        """
        try:
            # No need to have the program crash and exit for a small error:
            time_parts = list(map(int, time.split(":")))
        except ValueError:
            print("Incorrect time format. Use M:S or H:M:S.")
        else:
            if len(time_parts) == 2:
                time_parts.insert(0, 0)  # 0 hours
            self.time = datetime.time(*time_parts)

            # !!! Ideally, the time would be set automatically in
            # Logic Pro as well, but I'm not sure how to do this.
        
            print("Time in recording set to {}.".format(self.time))

    def do_play(self, arg):
        """
        Start playing the recording in Logic Pro, and record annotations.
        """

        # !!!! Display list of annotations (last ones before the timer, next
        # one after the timer)
        
        # !!!!! Send *play* command
        
        # !!!! Loop: display timer, get and execute annotation command

            # Real-time annotation commands:
            # - stop counting time & annotating (return to shell commands)
            # - delete last annotation
            # - commands from annotation_keys

            # Real-time display (curses module?):
            # - Annotations before the current point.
            # - Current, running time    
            # - Next annotation
        
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



