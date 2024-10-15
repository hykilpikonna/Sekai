from pathlib import Path
from typing import Any, Literal

import toml
from hypy_utils import SafeNamespace
from hypy_utils.logging_utils import setup_logger
from starlette.config import environ

log = setup_logger()

HOST_ADDR = 'http://10.0.0.17:19824'


class InfluxConfig:
    url: str
    token: str
    org: str
    bucket: str
    user: str


class DeviceConfig:
    adb_serial: str
    screen_size: tuple[int, int]
    corner_ld: tuple[int, int]
    corner_lt: tuple[int, int]
    corner_rt: tuple[int, int]
    corner_rd: tuple[int, int]
    early_late_px: tuple[int, int]
    visual_y: int
    visual_y2: int
    delay: float
    delay_2: float
    touch_y: int
    bitrate: int
    fps: int


class Config:
    device: DeviceConfig
    influx: InfluxConfig
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


config_paths = ['config.toml', 'automata/config.toml']
if environ.get('CONFIG_PATH'):
    config_paths = [environ['CONFIG_PATH']]
config: Config = [toml_to_namespace(Path(f).read_text('utf-8')) for f in config_paths
                  if Path(f).is_file()][0]

# Valid keys: 'playing'
global_dict = {}


def get_mode() -> Literal['host', 'helper', 'self']:
    return environ.get('MODE', 'host')


def get_log_path() -> Path:
    return Path(environ.get('LOG_PATH', 'log'))
