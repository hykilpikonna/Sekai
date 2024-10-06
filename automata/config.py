from pathlib import Path
from typing import Any

import toml
from hypy_utils import SafeNamespace
from hypy_utils.logging_utils import setup_logger

log = setup_logger()


class DeviceConfig:
    adb_serial: str
    screen_size: tuple[int, int]
    corner_ld: tuple[int, int]
    corner_lt: tuple[int, int]
    corner_rt: tuple[int, int]
    corner_rd: tuple[int, int]
    visual_y: int
    visual_y2: int
    delay: float
    delay_2: float
    touch_y: int
    bitrate: int
    fps: int


class Config:
    device: DeviceConfig
    debug: bool
    image_threshold: float
    frame_delay: float
    music_path: str


def toml_to_namespace(s: str) -> Any:
    # Parse the TOML string into a dictionary
    parsed_toml = toml.loads(s)
    # Convert the dictionary into a SafeNamespace object
    return _dict_to_namespace(parsed_toml)


def _dict_to_namespace(d: dict) -> SafeNamespace:
    # Recursively convert dictionaries into SafeNamespace objects
    return SafeNamespace(**{k: _dict_to_namespace(v) if isinstance(v, dict) else v for k, v in d.items()})


config: Config = [toml_to_namespace(Path(f).read_text('utf-8')) for f in ['config.toml', 'automata/config.toml']
                  if Path(f).is_file()][0]

global_dict = {}
