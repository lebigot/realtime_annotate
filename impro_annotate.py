#!/usr/bin/env python3.2

"""
Annotations tagged with a timestamp.

Ad hoc annotations for judging a long string of pieces.
"""

import collections
import enum

# Timestamped annotation:
TimedAnnotation = collections.namedtuple("TimedAnnotation", "time annotation")

# !!!!!!!!! Ideally, I would check my listening notes for my CD and
# also for 2014-6-21, to know what kind of annotations I make. For
# instance, maybe adding some level indication (optional) would be
# good, like inspired 2 (meaning "a lot", or something), or "glitch 1"
# (small) or "glitch 2" (big).

class Annotation(enum.Enum):
    """Annotation types, along with their (keyboard) key."""

    # Multiple pieces handling:
    cut = "c"  # Between pieces

    # Musicality:
    uninspired = "u"  # Musically uninspired
    inspired = "i"  # Musically inspired

    # Technical correctness:
    small_tech_glitch = "s"  # Small technical glitch
    big_tech_glitch = "b"  # Big technical glitch

def annotate():
    """
    Display a time counter and records timestamped annotations.

    Returns a list of TimedAnnotations, where the annotations are of
    the Annotations class.
    """

    annotations = []

    commands = {annotation.value: annotation for annotation in Annotation}

    print("* Available annotations:")
    for key in sorted(commands):
        print("{}: {}".format(key, commands[key].name))

    
    #!!!!!!!!
    
if __name__ == "__main__":

    import argparse
    import pickle

    parser = argparse.ArgumentParser(description="Timed annotations.")
    parser.add_argument("annotation_file")
    args = parser.parse_args()

    # !!!!!!! Offer to add annotations to existing file (an
    # interactive display of the next annotation to come would be
    # great, in order to avoid duplicates)

    # !!!!! Having a command to jump to a certain timestamp would be
    # useful (e.g. for completing work)

    annotations = annotate()

    with open(args.annotation_file, "wb") as out_file:
        pickle.dump(annotations, out_file)
