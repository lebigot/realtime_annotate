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
    
Annotation = enum.Enum(annotation_keys.values())

# Timestamped annotation:
TimedAnnotation = collections.namedtuple("TimedAnnotation", "time annotation")


# !!!!!!!!!!!! I guess that the best interface would actually be a 
# shell. The shell command would be: start annotating (at zero time by 
# default, at time settable by the user otherwise) [which runs an 
# annotation loop that can be quit and returns to the shell]; edit 
# annotations (probably stored as a text file, then, maybe in YAML); 
# save annotations (with an automatic prompted save a the end). Load an 
# annotation file (can also be given in the command line) for update.

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
