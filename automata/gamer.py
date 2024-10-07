import math
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from scrcpy import ACTION_MOVE, Client, ACTION_UP, ACTION_DOWN
from hypy_utils import printc
from numpy import ndarray

from . import util
from .config import config, global_dict

dev = config.device


def lc_rc(y: int) -> tuple[int, int]:
    return util.intersection(dev.corner_ld, dev.corner_lt, y), util.intersection(dev.corner_rd, dev.corner_rt, y)


# Calculate the visual corners
touch_lc, touch_rc = lc_rc(dev.touch_y)

# Pre-calculate touch positions for each 12 touch areas (this would be 13 values)
touch_positions = list(range(touch_lc, touch_rc + 1, (touch_rc - touch_lc) // 12))
air_delta = 400
air_time_delta = 50
light_threshold = int(0.7 * 255)

# Colors for late/early
late_early_px = (1017, 604)
late = np.array((252, 85, 139))[[2, 1, 0]]
fast = np.array((85, 170, 255))[[2, 1, 0]]
late_early_ms = 1
late_early_save = Path(__file__).parent / "delay.txt"


def interpolate_y() -> tuple[list[tuple[int, int]], tuple[ndarray, ndarray], list[int], list[float]]:
    """
    We have the visual_y representing the start line of the note detection, and visual_y2 representing
    the end. We want to interpolate 10 lines in between, and on each line, 12 points.

    :return: A flattend 1d list of (x, y) coordinates, A numpy query that gives you the points when used on frame,
        A list of y coordinates, A list of delays
    """
    ny = 11
    y = np.linspace(dev.visual_y, dev.visual_y2, ny).astype(int).tolist()
    delays = np.linspace(dev.delay, dev.delay_2, ny).tolist()
    pt = [[(x, y) for x in range(lc + (rc - lc) // 24, rc, (rc - lc) // 12)]
          for y, (lc, rc) in {y: lc_rc(y) for y in y}.items()]
    flat = list(([p for row in pt for p in row]))
    rows, cols = zip(*flat)
    query = (np.array(rows), np.array(cols))
    return flat, query, y, delays


ys = interpolate_y()


class SekaiGamer:
    # Music notes data
    taps: list[dict]
    slides: list[list[dict]]

    # In-game time in nanoseconds
    igt: int = 0
    started: bool = False
    done: bool = False

    # Queue of air notes to be flicked (start ela time, lane, touch_id)
    air_queue: list[tuple[int, int, int]] = []
    slide_ongoing: list[list[dict]] = []
    y = dev.touch_y

    # Late: decrease, Fast: increase
    late_early_total = 0
    late_early_last_adjust = 0

    def __init__(self, client: Client, notes: dict):
        self.client = client
        self.taps, self.slides = notes['taps'], notes['slides']

        def norm_lane(t):
            lane = t['lane'] - 2
            t['tpo'] = (touch_positions[lane] + touch_positions[lane + t['width']]) / 2
            if t['r'] == 'air' or (t.get('airNote') and t['airNote'].get('type') == 'flick'):
                t['t'] -= air_time_delta / 2

        [norm_lane(t) for t in self.taps]
        [norm_lane(t) for s in self.slides for t in s]

    def touch(self, x: int | float, y: int | float, action: int, tid: int):
        self.client.control.touch(int(round(x)), int(round(y)), action, tid)

    def adjust(self, is_fast: bool, is_late: bool) -> None:
        """ Adjust fast or late by diff ms """
        diff = [0, -1, 1][is_late * 1 + is_fast * 2] * late_early_ms
        self.igt += diff * 1_000_000
        self.late_early_total += diff
        self.late_early_last_adjust = int(time.time_ns() - self.igt) / 1_000_000
        diff != 0 and printc(f'{'&cLate: -' if is_late else '&bFast: +'}{abs(diff)} ms')

    def find_start(self, frame: ndarray) -> None:
        """ Find if we're ready to start """
        gray: ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).T

        # Find if one match is found
        points = gray[ys[1]] > light_threshold
        if not np.any(points):
            return

        # Find index where the first match is found
        first = np.argmax(points, axis=0)
        y = ys[0][first][1]
        delay = ys[3][ys[2].index(y)]

        # Start
        self.started = True
        self.igt = int(time.time_ns() + delay * 1_000_000)

        # Remove the first note's start time from igt
        self.igt -= min(self.taps[0]['t'], self.slides[0][0]['t']) * 1_000_000

        print("Playing")
        # For debug: draw a line on the visual line and save the frame
        gray[ys[1]] = 255
        date = time.strftime("%Y%m%d-%H%M%S")
        Path("log").mkdir(exist_ok=True)
        cv2.imwrite(f"log/{date}.webp", gray.T)

    def on_frame(self, frame: ndarray) -> None:
        # Elapsed ms since the start
        ela = int((time.time_ns() - self.igt) / 1_000_000)
        if ela < 0 or frame is None or self.done:
            return

        # Hasn't started yet
        if not self.started:
            self.find_start(frame)
            return

        # Detect late/early (in-between delay 0.3s)
        if self.late_early_last_adjust + 300 < ela:
            color = frame[late_early_px[1], late_early_px[0]]
            self.adjust(np.linalg.norm(color - fast) < 30, np.linalg.norm(color - late) < 30)

        # Pop any note that is ready to be played
        todo = []
        while self.taps and self.taps[0]['t'] < ela:
            todo.append(self.taps.pop(0))

        # Flick air notes
        for t in list(self.air_queue):
            end, tpo, tid = t
            # Check if it's done
            if end < ela:
                self.touch(tpo, self.y - air_delta, ACTION_UP, tid)
                self.air_queue.remove(t)
                continue
            # Interpolate the position
            y = self.y - air_delta + (self.y - air_delta - self.y) * (ela - t[0]) / air_time_delta
            self.touch(tpo, y, ACTION_MOVE, tid)

        # Play the notes
        for t in todo:
            tid, tpo = t['tid'], t['tpo']
            if t['r'] == 'short':
                self.touch(tpo, self.y, ACTION_DOWN, tid)
                self.touch(tpo, self.y, ACTION_UP, tid)
            elif t['r'] == 'air':
                self.touch(tpo, self.y, ACTION_DOWN, tid)
                self.air_queue.append((ela + air_time_delta, tpo, tid))
            else:
                print("Unknown note type", t)

        # Ongoing slides: move to interpolated position
        for slide in list(self.slide_ongoing):
            tid = slide[0]['tid']
            if len(slide) == 1:
                # If we're ready to finish
                t = slide[0]
                if t['t'] < ela:
                    tid, tpo = t['tid'], t['tpo']
                    if t.get('airNote') and t['airNote'].get('type') == 'flick':
                        # Add to flick queue
                        self.air_queue.append((ela + air_time_delta, tpo, tid))
                    else:
                        self.touch(tpo, self.y, ACTION_UP, tid)
                    self.slide_ongoing.remove(slide)
                continue

            t_from, t_to = slide[0], slide[1]
            po_from, po_to = t_from['tpo'], t_to['tpo']
            # If we're ready to move to the next note
            if t_to['t'] < ela:
                slide.pop(0)
                self.touch(po_to, self.y, ACTION_MOVE, tid)
                continue

            # Move to interpolated position
            time_delta = t_to['t'] - t_from['t']
            ratio = (ela - t_from['t']) / time_delta
            po_diff = po_to - po_from
            # Check if it's linear or sin
            if t_from.get('airNote') and 'bend' in t_from['airNote'].get('type'):
                if t_from['airNote']['type'] == 'slide bend middle':
                    po = po_diff * (1 - math.sin(ratio * math.pi / 2 + math.pi / 2)) + po_from
                else:
                    po = po_diff * math.sin(ratio * math.pi / 2) + po_from
            else:
                po = po_diff * ratio + po_from
            self.touch(po, self.y, ACTION_MOVE, tid)

        # Slides
        while self.slides and self.slides[0][0]['t'] < ela:
            slide = self.slides.pop(0)
            self.slide_ongoing.append(slide)
            # Press the first note
            t = slide[0]
            tid, tpo = t['tid'], t['tpo']
            self.touch(tpo, self.y, ACTION_DOWN, tid)

        # If everything is done, unset global_dict['playing']
        if not self.taps and not self.slides and not self.slide_ongoing and not self.air_queue:
            printc(f"&aDone! Total delay adjusted: {self.late_early_total} ms")
            threading.Thread(target=exit_thread).start()
            self.done = True


def exit_thread():
    time.sleep(5)
    os._exit(0)
