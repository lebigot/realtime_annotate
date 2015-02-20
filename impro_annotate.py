#!/usr/bin/env python3.4

"""
Annotations tagged with a timestamp.

Ad hoc annotations for judging a long string of pieces.
"""

import collections
import enum
import pickle
import pathlib

# File that contains the annotations. It contains a mapping from piece
# references to their annotations.
ANNOTATIONS_PATH = pathlib.Path("annotations.pickle")

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
        

def annotate_loop(args):
    """
    Display a time counter and records timestamped annotations.

    args -- command-line arguments of the annotate command.
    """

    # !!!!!! Think about the interface structure: two modes (command
    # [in shell?], with information setting and display? and
    # annotating in real-time)?

    # Shell commands (cmd module?):
    # - start counting time & annotating    
    # - set the counter time (default = last annotation, or 0)
    # - quit annotating (and save annotations to file)
    
    # Real-time annotation commands:
    # - stop counting time & annotating (return to shell commands)
    # - delete last annotation
    # - commands from annotation_keys

    # Real-time display (curses module?):
    # - Annotations before the current point.
    # - Current, running time    
    # - Next annotation

    # !!!!!! Implement
    return

def list_pieces(args):
    """
    List pieces that are already annotated.

    args -- command-line arguments of the list command (ignored).
    """
    with ANNOTATIONS_PATH.open("rb") as annotations_file:
        annotations = pickle.load(annotations_file)
    print("Annotated pieces (by sorted reference):")
    for piece_ref in sorted(annotations):
        print("- {}".format(piece_ref))

if __name__ == "__main__":
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Timestamped musical annotations.")

    subparsers = parser.add_subparsers()

    parser_annotate = subparsers.add_parser("annotate", help="annotate piece")
    parser_annotate.add_argument(
        "piece_ref",
        help="Reference to the piece to be annotated")
    parser_annotate.set_defaults(func=annotate_loop)
    
    parser_list = subparsers.add_parser(
        "list", help="list references of annotated pieces")
    parser_list.set_defaults(func=list_pieces)
    
    args = parser.parse_args()

    ####################

    # The annotations file is created, if it does not already exist:
    print("Annotations file: {}.".format(ANNOTATIONS_PATH))
    
    # The annotation file is created if it does not exist:
    if not ANNOTATIONS_PATH.exists():
        # An empty annotation database is created:
        with ANNOTATIONS_PATH.open("wb") as annotations_file:
            pickle.dump({}, annotations_file)

    # Execution of the function set for the chosen command:
    try:
        args.func(args)
    except AttributeError:
        # No command given
        parser.error("Please provide a command.")



