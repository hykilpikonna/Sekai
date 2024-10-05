import inspect
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import toml
from hypy_utils import SafeNamespace
from numpy import ndarray

from .config import DEBUG


def intersection(corner1: tuple[int, int], corner2: tuple[int, int], y_line: int) -> int:
    """
    Calculate the x-intercept of a line that intersects the given y-line

    :param corner1: The first corner of the line (x, y)
    :param corner2: The second corner of the line (x, y)
    :param y_line: The y-line to intersect
    :return: The x-intercept of the line
    """
    x1, y1 = corner1
    x2, y2 = corner2

    if y1 == y2:  # If the line is horizontal, there's no slant to intersect
        raise ValueError(f"The line is horizontal, there's no slant to intersect (input: {corner1}, {corner2}, {y_line})")

    # Calculate slope (m)
    slope = (y2 - y1) / (x2 - x1)

    # Calculate x-intercept for the given y = y_line
    x_intercept = x1 + (y_line - y1) / slope

    return int(x_intercept)


def img(name: str) -> ndarray:
    """
    Load an image resource

    :param name: The name of the image
    :return: The image as a numpy array
    """
    path = Path(__file__).parent / name
    if path.is_file():
        return cv2.imread(str(path))
    path = Path(name)
    if path.is_file():
        return cv2.imread(str(path))
    caller = inspect.getmodule(inspect.stack()[1][0]).__file__
    path = Path(caller).parent / name
    if path.is_file():
        return cv2.imread(str(path))

    raise FileNotFoundError(f"Image {name} not found")


def locate(source: ndarray, wanted: ndarray, accuracy: float = 0.90, center: bool = True) -> tuple[int, int] | None:
    """
    从 source 图片中查找 wanted 图片所在的位置，当置信度大于 accuracy 时返回找到的最大置信度位置的左上角坐标

    :param source: 源图片
    :param wanted: 待查找的图片
    :param accuracy: 最低置信度 [0, 1]
    :param center: 是否返回目标中心坐标
    :return: 找到的位置的左上角坐标
    """
    result = cv2.matchTemplate(source, wanted, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= accuracy:
        # Debug: Draw the bounding rect of the found image
        if DEBUG:
            h, w = wanted.shape[:-1]
            cv2.rectangle(source, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 0, 255), 2)

        return center_of(wanted.shape, max_loc) if center else max_loc
    else:
        return None


def locate_all(source: ndarray, wanted: ndarray, accuracy: float = 0.90) -> list[tuple[int, int]]:
    """
    从 source 图片中查找 wanted 图片所在的位置，当置信度大于 accuracy 时返回找到的所有位置的左上角坐标（自动去重）

    :param source: 源图片
    :param wanted: 待查找的图片
    :param accuracy: 最低置信度 [0, 1]
    :return: 找到的位置的左上角坐标
    """
    loc_pos = []

    result = cv2.matchTemplate(source, wanted, cv2.TM_CCOEFF_NORMED)
    location = np.where(result >= accuracy)

    ex, ey = 0, 0
    for pt in zip(*location[::-1]):
        x = pt[0]
        y = pt[1]

        if (x - ex) + (y - ey) < 15:  # 去掉邻近重复的点
            continue
        ex, ey = x, y

        loc_pos.append((int(x), int(y)))

    return loc_pos


def center_of(wanted_size: tuple[int, int, int], top_left: tuple[int, int]) -> tuple[int, int] | None:
    """
    给定目标尺寸大小和目标左上角顶点坐标，即可给出目标中心的坐标

    :param wanted_size:
    :param top_left:
    :return:
    """
    tl_x, tl_y = top_left
    h_src, w_src, _ = wanted_size
    if tl_x < 0 or tl_y < 0 or w_src <= 0 or h_src <= 0:
        return None

    return int(tl_x + w_src / 2), int(tl_y + h_src / 2)


def toml_to_namespace(s: str) -> Any:
    # Parse the TOML string into a dictionary
    parsed_toml = toml.loads(s)
    # Convert the dictionary into a SafeNamespace object
    return _dict_to_namespace(parsed_toml)


def _dict_to_namespace(d: dict) -> SafeNamespace:
    # Recursively convert dictionaries into SafeNamespace objects
    return SafeNamespace(**{k: _dict_to_namespace(v) if isinstance(v, dict) else v for k, v in d.items()})
