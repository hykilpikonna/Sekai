from pathlib import Path

import scrcpy
from adbutils import adb, AdbDevice
from scrcpy import LOCK_SCREEN_ORIENTATION_1

from .config import Config
from .util import toml_to_namespace


def on_frame(frame: bytes):
    pass


def run():
    # Find device
    devices = adb.device_list()
    device = [v for v in devices if v.serial == config.device.adb_serial]
    if not device:
        raise ValueError(f"Device with serial {config.device.adb_serial} not found. Available devices: {devices}")

    # Connect to device
    client = scrcpy.Client(
        device=device[0],
        lock_screen_orientation=LOCK_SCREEN_ORIENTATION_1,
        max_fps=config.device.fps,
        bitrate=config.device.bitrate,
        max_width=config.device.screen_size[0]
    )

    client.add_listener(scrcpy.EVENT_INIT, lambda: print("Client started"))
    client.add_listener(scrcpy.EVENT_FRAME, on_frame)

    # Start the client
    client.start()


if __name__ == '__main__':
    config: Config = toml_to_namespace(Path("config.toml").read_text())
    run()
