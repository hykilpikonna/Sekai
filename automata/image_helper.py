"""
Source: https://github.com/hanmin0822/RaphaelScriptHelper/blob/master/ImageProc.py
"""
import cv2
import numpy
from numpy import ndarray


def locate(source: ndarray, wanted: ndarray, accuracy: float = 0.90) -> tuple[int, int] | None:
    """
    从 source 图片中查找 wanted 图片所在的位置，当置信度大于 accuracy 时返回找到的最大置信度位置的左上角坐标

    :param source: 源图片
    :param wanted: 待查找的图片
    :param accuracy: 最低置信度 [0, 1]
    :return: 找到的位置的左上角坐标
    """
    result = cv2.matchTemplate(source, wanted, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= accuracy:
        return max_loc
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
    location = numpy.where(result >= accuracy)

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
