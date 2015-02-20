#!/usr/bin/env python3.4

"""
Annotations tagged with a timestamp.

Ad hoc annotations for judging a long string of pieces.
"""

import collections
import enum

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
        

def annotate_loop():
    # !!!!!!! Check/update this function
    """
    Display a time counter and records timestamped annotations.

    Returns a list of TimedAnnotations, where the annotations are of
    the Annotations class.
    """

    return

    # !!!!!!!!!!!! I guess that the best interface would actually be a 
    # shell. The shell command would be: start annotating (at zero time by 
    # default, at time settable by the user otherwise) [which runs an 
    # annotation loop that can be quit and returns to the shell]; edit 
    # annotations (probably stored as a text file, then, maybe in YAML); 
    # save annotations (with an automatic prompted save a the end). Load an 
    # annotation file (can also be given in the command line) for update.


    # !!!!!!! Offer to add annotations to existing file (an
    # interactive display of the next annotation to come would be
    # great, in order to avoid duplicates)

    # !!!!! Having a command to jump to a certain timestamp would be
    # useful (e.g. for completing work)
    
    annotations = []

    commands = {annotation.value: annotation for annotation in Annotation}

    print("* Available annotations:")
    for key in sorted(commands):
        print("{}: {}".format(key, commands[key].name))

    
    #!!!!!!!!
    
if __name__ == "__main__":
    
    import pathlib
    import argparse
    import pickle
    
    parser = argparse.ArgumentParser(
        description="Timestamped musical annotations.")

    subparsers = parser.add_subparsers()

    subparsers.add_parser(
        "list", help="list references of annotated pieces")

    parser_annotate = subparsers.add_parser("annotate", help="annotate piece")
    parser_annotate.add_argument(
        "piece_ref",
        help="Reference to the piece to be annotated")
    
    args = parser.parse_args()

    ####################

    # The annotations file is created, if it does not already exist:
    annotation_file_path = pathlib.Path("annotations.pickle")
    print("Annotations stored in file {}.".format(annotation_file_path))
    
    # The annotation file is created if it does not exist:
    if not annotation_file_path.exists():
        # An empty annotation database is created:
        with annotation_file_path.open("wb") as annotations_file:
            pickle.dump({}, annotations_file)

    annotate_loop()



