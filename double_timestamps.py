#!/usr/bin/env python

"""
Double the timestamps of a given event in a realtime_annotate.py annotation
file.
"""


if __name__ == "__main__":

    import argparse

    import realtime_annotate

    parser = argparse.ArgumentParser()

    parser.add_argument("file_path", help="Annotation file path.")
    parser.add_argument("event_ref", help="Event reference.")
    parser.add_argument(
        "offset", nargs="?", default=realtime_annotate.Time(hours=1),
        type=lambda HMS_str: realtime_annotate.Time.from_HMS(
            [float(part) for part in HMS_str.split(":")]),
        help="Offset for the start of the event (HH:MM:SS, default 1:0:0).")

    args = parser.parse_args()

    annotations = realtime_annotate.Annotations(args.file_path)

    for annotation in annotations.all_event_data[args.event_ref]:
        orig_time = annotation.time
        new_time = args.offset+(orig_time-args.offset)*2
        print(orig_time, "->", new_time)
        annotation.time = new_time

    backup = annotations.save(args.file_path)
    print("Annotations updated.")
    print(f"Backup: {backup}.")
