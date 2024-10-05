import time

import numpy as np
import scrcpy
from adbutils import adb
import cv2
from numba.cuda import detect
from numpy import ndarray
from scrcpy import LOCK_SCREEN_ORIENTATION_1

import util

display = True

# One frame size (on my reference device)
ref_size = (1080, 544)
# Trapezoid corners
corner_ld = (67, 543)
corner_lt = (518, 0)
corner_rt = (563, 0)
corner_rd = (1012, 543)
# Where vertically does the bot look at
visual_y = 100
# Where do I touch
touch_y = 427

button_light_threshold = int(255 * 0.8)

# Calculate the visual corners
visual_lc: int = util.intersection(corner_ld, corner_lt, visual_y)
visual_rc: int = util.intersection(corner_rd, corner_rt, visual_y)
touch_lc: int = util.intersection(corner_ld, corner_lt, touch_y)
touch_rc: int = util.intersection(corner_rd, corner_rt, touch_y)

# touch_areas[i][time] is True if the i-th area is touched at time
time_max = 128
touch_areas = np.ndarray((6, time_max), dtype=bool)
# current time index for touch_areas
time_i = 0

last_tick = 0

# Pre-calculate touch positions for each 12 touch areas
tmp = (touch_rc - touch_lc) // 6
touch_positions = list(range(touch_lc + tmp // 2, touch_rc, tmp))
states = [False] * 6


def touch():
    # Touch the screen based on the last touch buffer
    # Get the last touch buffer
    touch_buffer = touch_areas[:, time_i - 1]
    # For each area that is true, touch the area
    for i, should_touch in enumerate(touch_buffer):
        if should_touch and not states[i]:
            client.control.touch(touch_positions[i], touch_y, touch_id=i, action=scrcpy.ACTION_DOWN)
            states[i] = True

    # Release all touches
    for i in range(len(states)):
        # For all already pressed buttons, release them
        if states[i]:
            client.control.touch(touch_positions[i], touch_y, touch_id=i, action=scrcpy.ACTION_UP)
            states[i] = False


def on_frame(frame: ndarray, should_touch: bool = True):
    global time_i, last_tick
    if frame is None:
        return

    # Tick igt, if the last tick is less than frame_delay ago, then skip
    start = time.time()

    # Grayscale frame efficiently using numpy
    gray: ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Touch the screen
    if should_touch:
        touch()

    # Get the visual line (a 1D line from visual_lc to visual_rc)
    v = gray[visual_y, visual_lc:visual_rc]

    # Separate the 1d line into 12 areas
    area_len = len(v) // 12
    det_pixels = list(range(area_len // 2, len(v), area_len))

    # If the area is lightened up, then it's touched
    # for i in det_pixels:
    #     touch_areas[i // area_len, time_i] = v[i] > button_light_threshold
    # If two areas are lightened up, then it's touched
    for i in range(0, len(states)):
        det_i = i * 2
        touch_areas[i, time_i] = v[det_pixels[det_i]] > button_light_threshold or \
                                 v[det_pixels[det_i + 1]] > button_light_threshold

    if display:
        # Draw boxes for each area that is lighted up
        for i in det_pixels:
            if v[i] > button_light_threshold:
                cv2.rectangle(gray, (visual_lc + i - area_len // 2, visual_y - 10),
                              (visual_lc + i + area_len // 2, visual_y + 10), 255, 2)

        # Draw the touch line and the visual line
        cv2.line(gray, (touch_lc, touch_y), (touch_rc, touch_y), 255, 2)
        cv2.line(gray, (visual_lc, visual_y), (visual_rc, visual_y), 255, 2)

        cv2.imshow("viz", gray)
        cv2.waitKey(1)

    # Update time index
    time_i = (time_i + 1) % time_max
    last_tick = time.time()
    print(f"{last_tick - start:.3f}s")

    pass


def test_frame():
    # Load frame from disk
    frame = np.load("frame.npy")
    on_frame(frame, False)
    exit(0)


def dummy_on_frame(frame: ndarray):
    if frame is None:
        return
    client.control.touch(100, 200, scrcpy.ACTION_DOWN, touch_id=0)
    client.control.touch(100, 200, scrcpy.ACTION_UP, touch_id=0)
    print("Frame received")


if __name__ == '__main__':
    # test_frame()

    # Connect to the device
    adb.connect('10.0.0.16:5555')
    client = scrcpy.Client(
        device=adb.device_list()[0],
        lock_screen_orientation=LOCK_SCREEN_ORIENTATION_1,
        max_fps=25,
        bitrate=1_000_000,
        max_width=1080
    )

    client.add_listener(scrcpy.EVENT_INIT, lambda: print("Client started"))
    # client.add_listener(scrcpy.EVENT_FRAME, dummy_on_frame)
    client.add_listener(scrcpy.EVENT_FRAME, on_frame)

    # Start the client
    client.start()
