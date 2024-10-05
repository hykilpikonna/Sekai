from pathlib import Path
from typing import Any

import toml
from hypy_utils import SafeNamespace
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
    image_threshold: float
    frame_delay: float


def toml_to_namespace(s: str) -> Any:
    # Parse the TOML string into a dictionary
    parsed_toml = toml.loads(s)
    # Convert the dictionary into a SafeNamespace object
    return _dict_to_namespace(parsed_toml)


def _dict_to_namespace(d: dict) -> SafeNamespace:
    # Recursively convert dictionaries into SafeNamespace objects
    return SafeNamespace(**{k: _dict_to_namespace(v) if isinstance(v, dict) else v for k, v in d.items()})


config: Config = [toml_to_namespace(Path(f).read_text()) for f in ['config.toml', 'automata/config.toml']
                  if Path(f).is_file()][0]
