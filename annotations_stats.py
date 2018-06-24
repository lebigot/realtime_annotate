#!/usr/bin/env python

"""
Print statistics on the given annotation file.
"""


if __name__ == "__main__":

    import argparse
    import datetime

    import realtime_annotate

    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", help="Annotation file path.")
    args = parser.parse_args()

    all_events = realtime_annotate.Annotations(args.file_path).all_event_data

    print("Number of events:", len(all_events))
    
    num_annotations = 0
    total_time = realtime_annotate.Time()

    for event_data in all_events.values():
        if event_data:
            num_annotations += len(event_data)
            total_time += event_data[-1].time - event_data[0].time

    print("Number of annotations:", num_annotations)
    print("Num. annovations/event:", num_annotations/len(all_events))
    print("Total annotation time (H:M:S):", total_time)
    print("Time/event:", total_time/len(all_events))
