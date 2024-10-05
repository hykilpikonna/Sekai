import math
import time
from pathlib import Path

import cv2
import numpy as np
import scrcpy
from numpy import ndarray

from . import util
from .config import config, global_dict

dev = config.device

# Calculate the visual corners
visual_lc: int = util.intersection(dev.corner_ld, dev.corner_lt, dev.visual_y)
visual_rc: int = util.intersection(dev.corner_rd, dev.corner_rt, dev.visual_y)
touch_lc: int = util.intersection(dev.corner_ld, dev.corner_lt, dev.touch_y)
touch_rc: int = util.intersection(dev.corner_rd, dev.corner_rt, dev.touch_y)

# Pre-calculate touch positions for each 12 touch areas (this would be 13 values)
touch_positions = list(range(touch_lc, touch_rc + 1, (touch_rc - touch_lc) // 12))
air_delta = 400
air_time_delta = 50
light_threshold = int(0.8 * 255)

# Colors for late/early
late_early_px = (1017, 604)
late = np.array((252, 85, 139))[[2, 1, 0]]
fast = np.array((85, 170, 255))[[2, 1, 0]]
late_early_ms = 0.5
late_early_save = Path(__file__).parent / "delay.txt"
# The time (seconds) from when a note appear to when it needs to be tapped
lane_speed = 22 / 30


class SekaiGamer:
    # Music notes data
    taps: list[dict]
    slides: list[list[dict]]

    igt: int = 0
    started: bool = False

    # Queue of air notes to be flicked (start ela time, lane, touch_id)
    air_queue: list[tuple[int, int, int]] = []
    slide_ongoing: list[list[dict]] = []
    y = dev.touch_y

    late_early_adjust = 150 * 1_000_000
    late_early_last_adjust = 0

    def __init__(self, client: scrcpy.Client, notes: dict):
        self.client = client
        self.load_song(notes)
        if late_early_save.exists():
            self.late_early_adjust = int(late_early_save.read_text().strip())
            print("Loaded late/early adjust:", self.late_early_adjust)

    def load_song(self, notes: dict):
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

        self.taps, self.slides = taps, slides

    def touch(self, x: int | float, y: int | float, action: int, tid: int):
        self.client.control.touch(int(round(x)), int(round(y)), action, tid)

    def on_frame(self, frame: ndarray) -> None:
        # Elapsed ms since the start
        ela = int((time.time_ns() - self.igt) / 1_000_000)
        if ela < 0 or frame is None:
            return

        # Hasn't started yet
        if not self.started:
            # Grayscale frame efficiently using numpy
            gray: ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Get the visual line (a 1D line from visual_lc to visual_rc)
            v = gray[dev.visual_y, visual_lc:visual_rc]

            # Separate the 1d line into 12 areas
            area_len = len(v) // 12
            det_pixels = list(range(area_len // 2, len(v), area_len))

            # If any area is lighted up, we are ready to play
            if any(v[i] > light_threshold for i in det_pixels):
                self.started = True
                # Late: decrease, Fast: increase
                # igt = time.time_ns() + 0.881 * 1_000_000_000
                # igt = time.time_ns() + 0.864 * 1_000_000_000
                # self.igt = int(time.time_ns() + 0.286 * 1_000_000_000)
                self.igt = int(time.time_ns() + 170 * 1_000_000)
                print("Playing")

            return

        # Detect late/early (in-between delay 0.5s)
        if self.late_early_last_adjust + 500 < ela:
            late_early = frame[late_early_px[1], late_early_px[0]]
            # Check distance should be less than 5
            if np.linalg.norm(late_early - late) < 30:
                print(f"Late, slowing down {late_early_ms} ms")
                self.igt -= late_early_ms * 1_000_000
                self.late_early_last_adjust = ela
            elif np.linalg.norm(late_early - fast) < 30:
                print(f"Fast, speeding up {late_early_ms} ms")
                self.igt += late_early_ms * 1_000_000
                self.late_early_last_adjust = ela

        # Pop any note that is ready to be played
        todo = []
        while self.taps and self.taps[0]['t'] < ela:
            todo.append(self.taps.pop(0))

        # Flick air notes
        for t in list(self.air_queue):
            end, tpo, tid = t
            # Check if it's done
            if end < ela:
                self.touch(tpo, self.y - air_delta, scrcpy.ACTION_UP, tid)
                self.air_queue.remove(t)
                continue
            # Interpolate the position
            y = self.y - air_delta + (self.y - air_delta - self.y) * (ela - t[0]) / air_time_delta
            self.touch(tpo, y, scrcpy.ACTION_MOVE, tid)

        # Play the notes
        for t in todo:
            tid, tpo = t['tid'], t['tpo']
            if t['r'] == 'short':
                self.touch(tpo, self.y, scrcpy.ACTION_DOWN, tid)
                self.touch(tpo, self.y, scrcpy.ACTION_UP, tid)
            elif t['r'] == 'air':
                self.touch(tpo, self.y, scrcpy.ACTION_DOWN, tid)
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
                    if t['airNote'] and t['airNote']['type'] == 'flick':
                        # Add to flick queue
                        self.air_queue.append((ela + air_time_delta, tpo, tid))
                    else:
                        self.touch(tpo, self.y, scrcpy.ACTION_UP, tid)
                    self.slide_ongoing.remove(slide)
                continue

            t_from, t_to = slide[0], slide[1]
            po_from, po_to = t_from['tpo'], t_to['tpo']
            # If we're ready to move to the next note
            if t_to['t'] < ela:
                slide.pop(0)
                self.touch(po_to, self.y, scrcpy.ACTION_MOVE, tid)
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
            self.touch(po, self.y, scrcpy.ACTION_MOVE, tid)

        # Slides
        while self.slides and self.slides[0][0]['t'] < ela:
            slide = self.slides.pop(0)
            self.slide_ongoing.append(slide)
            # Press the first note
            t = slide[0]
            tid, tpo = t['tid'], t['tpo']
            self.touch(tpo, self.y, scrcpy.ACTION_DOWN, tid)

        # If everything is done, unset global_dict['playing']
        if not self.taps and not self.slides and not self.slide_ongoing:
            print("Done")
            del global_dict['playing']
            late_early_save.write_text(str(self.late_early_adjust))
