from pathlib import Path

import toml
from hypy_utils import jsn
from hypy_utils.logging_utils import setup_logger

log = setup_logger()


class DeviceConfig:
    adb_serial: str
    screen_size: list[int]
    corner_ld: list[int]
    corner_lt: list[int]
    corner_rt: list[int]
    corner_rd: list[int]
    visual_y: int
    touch_y: int
    bitrate: int
    fps: int


class Config:
    device: DeviceConfig
    debug: bool
