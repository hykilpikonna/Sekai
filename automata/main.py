import json
import math
import time
from enum import Enum
from pathlib import Path

import cv2
import numpy as np
import scrcpy
from adbutils import adb
from numpy import ndarray
from scrcpy import LOCK_SCREEN_ORIENTATION_1

import util

display = False
debug_simulation = False

touch_events = []


def touch(x, y, action, tid):
    # Log touch events
    if not debug_simulation:
        client.control.touch(int(round(x)), int(round(y)), action, tid)
    else:
        touch_events.append({'x': x, 'y': y, 'action': action, 'tid': tid, 'time': time.time_ns()})
        print(f"Touch event: {action} at ({x}, {y}) with tid {tid}")


# One frame size (on my reference device)
ref_size = (1080, 544)
# Trapezoid corners
corner_ld = (67, 543)
corner_lt = (518, 0)
corner_rt = (563, 0)
corner_rd = (1012, 543)
# Where vertically does the bot look at
visual_y = 100
# visual_y = 400
# Where do I touch
touch_y = 500

button_light_threshold = int(255 * 0.8)

# Calculate the visual corners
visual_lc: int = util.intersection(corner_ld, corner_lt, visual_y)
visual_rc: int = util.intersection(corner_rd, corner_rt, visual_y)
touch_lc: int = util.intersection(corner_ld, corner_lt, touch_y)
touch_rc: int = util.intersection(corner_rd, corner_rt, touch_y)

# Pre-calculate touch positions for each 12 touch areas (this would be 13 values)
touch_positions = list(range(touch_lc, touch_rc + 1, (touch_rc - touch_lc) // 12))


class AState(Enum):
    WAIT_INIT = 0  # Waiting for the first note
    PLAYING = 1  # Playing the notes


state: AState = AState.WAIT_INIT
igt = time.time_ns()
notes: dict
taps: list[dict]
slides: list[list[dict]]
air_delta = 400
air_time_delta = 80
# Queue of air notes to be flicked (start ela time, lane, touch_id)
air_queue: list[tuple[int, int, int]] = []
slide_ongoing: list[list[dict]] = []


def load_song():
    global notes, taps, slides
    notes = json.loads(Path('sus2json/expert-parsed.json').read_text())
    taps = notes['timestampNotes']
    taps = [t for t in taps if 2 <= t['lane'] <= 13 and t['type'] != 'diamond' and t['r'] in {'short', 'air'}]

    def norm_lane(t):
        lane = t['lane'] - 2
        t['tpo'] = (touch_positions[lane] + touch_positions[lane + t['width']]) / 2
    tid = 0
    for t in taps:
        tid += 1
        norm_lane(t)
        t['tid'] = tid
        # Reduce 5ms for flicks
        # if t['r'] == 'air':
        #     t['t'] -= 5
    slides = [s for s in notes['slides'] if s]
    for s in slides:
        tid += 1
        for t in s:
            norm_lane(t)
            t['tid'] = tid
            # if t['airNote'] and t['airNote']['type'] == 'flick':
                # t['t'] -= 5


def on_frame(frame: ndarray):
    if frame is None:
        return
    global igt, state
    # Elapsed ms since the start
    ela = int((time.time_ns() - igt) / 1_000_000)
    if ela < 0:
        return

    if display:
        cv2.imshow('frame', frame)
        cv2.waitKey(1)

    if state == AState.WAIT_INIT:
        # Grayscale frame efficiently using numpy
        gray: ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Get the visual line (a 1D line from visual_lc to visual_rc)
        v = gray[visual_y, visual_lc:visual_rc]

        # Separate the 1d line into 12 areas
        area_len = len(v) // 12
        det_pixels = list(range(area_len // 2, len(v), area_len))

        # If any area is lighted up, we are ready to play
        if any(v[i] > button_light_threshold for i in det_pixels) or debug_simulation:
            state = AState.PLAYING
            # Late: decrease, Fast: increase
            # igt = time.time_ns() + 0.881 * 1_000_000_000
            # igt = time.time_ns() + 0.864 * 1_000_000_000
            igt = time.time_ns() + 0.286 * 1_000_000_000
            print("Playing")

    elif state == AState.PLAYING:
        # Pop any note that is ready to be played
        todo = []
        while taps and taps[0]['t'] < ela:
            todo.append(taps.pop(0))

        # Flick air notes
        for t in list(air_queue):
            end, tpo, tid = t
            # Check if it's done
            if end < ela:
                touch(tpo, touch_y - air_delta, scrcpy.ACTION_UP, tid)
                air_queue.remove(t)
                continue
            # Interpolate the position
            y = touch_y - air_delta + (touch_y - air_delta - touch_y) * (ela - t[0]) / air_time_delta
            touch(tpo, y, scrcpy.ACTION_MOVE, tid)

        # Play the notes
        for t in todo:
            tid, tpo = t['tid'], t['tpo']
            if t['r'] == 'short':
                touch(tpo, touch_y, scrcpy.ACTION_DOWN, tid)
                touch(tpo, touch_y, scrcpy.ACTION_UP, tid)
            elif t['r'] == 'air':
                touch(tpo, touch_y, scrcpy.ACTION_DOWN, tid)
                air_queue.append((ela + air_time_delta, tpo, tid))
            else:
                print("Unknown note type", t)

        # Ongoing slides: move to interpolated position
        for slide in list(slide_ongoing):
            tid = slide[0]['tid']
            if len(slide) == 1:
                # If we're ready to finish
                t = slide[0]
                if t['t'] < ela:
                    tid, tpo = t['tid'], t['tpo']
                    if t['airNote'] and t['airNote']['type'] == 'flick':
                        # Add to flick queue
                        air_queue.append((ela + air_time_delta, tpo, tid))
                    else:
                        touch(tpo, touch_y, scrcpy.ACTION_UP, tid)
                    slide_ongoing.remove(slide)
                continue

            t_from, t_to = slide[0], slide[1]
            po_from, po_to = t_from['tpo'], t_to['tpo']
            # If we're ready to move to the next note
            if t_to['t'] < ela:
                slide.pop(0)
                touch(po_to, touch_y, scrcpy.ACTION_MOVE, tid)
                continue

            # Move to interpolated position
            time_delta = t_to['t'] - t_from['t']
            ratio = (ela - t_from['t']) / time_delta
            po_diff = po_to - po_from
            # Check if it's linear or sin
            if t_from['airNote'] and 'bend' in t_from['airNote']['type']:
                if t_from['airNote']['type'] == 'slide bend middle':
                    po = po_diff * (1 - math.sin(ratio * math.pi / 2 + math.pi / 2)) + po_from
                else:
                    po = po_diff * math.sin(ratio * math.pi / 2) + po_from
            else:
                po = po_diff * ratio + po_from
            touch(po, touch_y, scrcpy.ACTION_MOVE, tid)

        # Slides
        while slides and slides[0][0]['t'] < ela:
            slide = slides.pop(0)
            slide_ongoing.append(slide)
            # Press the first note
            t = slide[0]
            tid, tpo = t['tid'], t['tpo']
            touch(tpo, touch_y, scrcpy.ACTION_DOWN, tid)

    pass


def test_frame():
    # Load frame from disk
    frame = np.load("frame.npy")
    on_frame(frame)
    exit(0)


def dummy_on_frame(frame: ndarray):
    if frame is None:
        return
    touch(100, 200, scrcpy.ACTION_DOWN, 0)
    touch(100, 200, scrcpy.ACTION_UP, 0)
    print("Frame received")


if __name__ == '__main__':
    # test_frame()
    load_song()

    # Connect to the device
    # adb.connect('10.0.0.16:5555')
    client = scrcpy.Client(
        device=adb.device_list()[0],
        lock_screen_orientation=LOCK_SCREEN_ORIENTATION_1,
        max_fps=60,
        bitrate=500_000,
        max_width=1080
    )
    touch = client.control.touch

    client.add_listener(scrcpy.EVENT_INIT, lambda: print("Client started"))
    # client.add_listener(scrcpy.EVENT_FRAME, dummy_on_frame)
    client.add_listener(scrcpy.EVENT_FRAME, on_frame)

    # Start the client
    client.start()
