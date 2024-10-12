import os
import threading
import time
from os import environ
from typing import Literal

import cv2
import numpy as np
import scrcpy
import uvicorn
from adbutils import adb
from fastapi import FastAPI
from numpy import ndarray
from scrcpy import LOCK_SCREEN_ORIENTATION_1

from .config import log, config, global_dict, HOST_ADDR, get_mode
from .gamer import SekaiGamer
from .models import SekaiStageContext, SekaiStage, SekaiStageOp
from .stage import find_stage, load_stages
from .util import priority_win, ImageFinder, ocr_extract_number

client: scrcpy.Client
ctx: SekaiStageContext = None
frame: ndarray = np.zeros((1, 1, 3), np.uint8)
frame_time = 0
last_find_stage = 0

ctx_lock = threading.Lock()
net = FastAPI()
img_mp_create_open = ImageFinder('mp_create_open')
img_mp_id = ImageFinder('bmp_id')


@net.get("/bmp_room_id")
def bmp_room_id():
    # Check if the current frame is mp_create_open
    if global_dict.get('playing') or not img_mp_create_open.check(ctx.frame_gray):
        return {"id": None}

    # Find the room id
    img = img_mp_id.get_region(ctx.frame)
    # OCR
    room_id = ocr_extract_number(img)
    # Zfill to 5
    room_id = str(room_id).zfill(5)

    return {"id": room_id}


def _loop():
    global ctx, last_find_stage

    # Check if last find stage is too recent (< 1s)
    if ctx.time - last_find_stage < 1000:
        return
    last_find_stage = ctx.time

    with ctx_lock:
        if not ctx.last_op_done:
            return

        # The context operation is complete, we need to look for the next stage
        stage = find_stage(ctx, stages)
        if not stage:
            # Check if timeout has been reached
            if ctx.time - ctx.last_op_done > ctx.last_op.next_stage_timeout * 1000:
                log.error(f"Timeout and have not found the next stage: {ctx.last_op.next_stage}")
                # Click
                w, h = config.device.screen_size
                tx, ty = w * 0.9, h * 0.9
                ctx.tap(tx, ty)
                ctx.tap(tx, ty)
                ctx.tap(tx, ty)
                # TODO: Handle timeout
                ctx.last_op_done = ctx.time
            return

        # Perform the operation
        log.info(f"[{ctx.time}] Entered stage {stage.name}")
        op = stage.operate(ctx)
        log.info(f"> Performing operation {op.name}")
        ctx.last_op = op
        ctx.last_op_done = None


def loop():
    while frame_time == 0:
        time.sleep(0.1)

    while True:
        if global_dict.get('playing'):
            time.sleep(1)
            continue

        st = time.time_ns()
        # Check frame timeout 10s
        if st - frame_time > 10_000_000_000:
            log.error("Frame timeout")
            os._exit(1)
        _loop()
        et = time.time_ns()
        log.debug(f"Loop time: {(et - st) / 1_000_000:.2f}ms")
        time.sleep(1)


def on_frame(new_frame: ndarray):
    """
    This is called when a new frame is received from the device
    """
    if new_frame is None:
        return

    # Gamer mode takes highest priority
    p: SekaiGamer = global_dict.get('playing')
    if p:
        p.on_frame(new_frame)
        return

    global ctx, frame_time, frame
    assert new_frame.shape == (config.device.screen_size[1], config.device.screen_size[0], 3), \
        f"Frame shape mismatch: {new_frame.shape} != {config.device.screen_size[1], config.device.screen_size[0], 3}"

    if config.debug:
        cv2.imshow("Sekai Automata", new_frame)
        cv2.waitKey(1)

    # Check if ctx_lock is locked
    if ctx_lock.locked():
        return

    frame = new_frame
    frame_time = time.time_ns()

    with ctx_lock:
        # Create the frame context
        ctx.next(frame)

        # If the context operation is not complete, continue the operation
        if ctx.last_op_done is None:
            ac = ctx.last_op.actions[ctx.last_op.action_i]
            # Update the action
            log.info(f"> Running action {type(ac).__name__} (started: {ac.started})")
            if not ac.run(ctx):
                return
            # It finished this time, move to the next action
            ctx.last_op.action_i += 1
            # Done with all actions in the operation
            if ctx.last_op.action_i >= len(ctx.last_op.actions):
                log.info(f"> Operation completed: {ctx.last_op.name}")
                ctx.last_op_done = ctx.time
            return


def control():
    # The control thread: Wait for user input
    while True:
        try:
            if input() == 'quit':
                os._exit(0)
        except (KeyboardInterrupt, EOFError):
            os._exit(0)


def uvicorn_thread():
    uvicorn.run(net, host="0.0.0.0", port=int(HOST_ADDR.split(":")[-1]))


def run(adb_serial: str = None):
    global client, ctx

    adb_serial = adb_serial or config.device.adb_serial or environ.get('ADB_SERIAL')

    # Find device
    devices = adb.device_list()
    device = [v for v in devices if v.serial == adb_serial] if adb_serial else devices
    if not device:
        raise ValueError(f"Device with serial {config.device.adb_serial} not found. Available devices: {devices}")

    # Connect to device
    client = scrcpy.Client(
        device=device[0],
        lock_screen_orientation=LOCK_SCREEN_ORIENTATION_1,
        max_fps=config.device.fps,
        bitrate=config.device.bitrate,
        max_width=config.device.screen_size[0],
    )

    ctx = SekaiStageContext(client, frame, {}, {}, time.time_ns() // 1_000_000, SekaiStageOp("startup", [], set()))

    def init():
        print("Client started")
        priority_win()

    client.add_listener(scrcpy.EVENT_INIT, init)
    client.add_listener(scrcpy.EVENT_FRAME, on_frame)

    # Start the client
    client.start(threaded=True)
    threading.Thread(target=control).start()
    if get_mode() == 'host':
        threading.Thread(target=uvicorn_thread).start()
    loop()


if __name__ == '__main__':
    stages: dict[str, SekaiStage] = load_stages()
    run()
