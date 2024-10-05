import inspect
import json
import pickle
import time
from pathlib import Path

import cv2
import imagehash
import numpy as np
import toml
from PIL import Image
from imagehash import ImageHash
from numpy import ndarray

from .config import config


def ncc_sim(a: ndarray, b: ndarray) -> float:
    """
    Compute the normalized cross-correlation between two arrays (images)

    NCC sim is much faster than SSIM, but also less accurate.

    In [97]: %time normalized_cross_correlation(part[:-2, :-2, 0], part[2:, 2:, 0])
    CPU times: user 63 µs, sys: 788 µs, total: 851 µs
    Wall time: 743 µs
    Out[97]: 0.9743215

    In [98]: %time ssim(part[:-2, :-2, 0], part[2:, 2:, 0])
    CPU times: user 8.49 ms, sys: 940 µs, total: 9.43 ms
    Wall time: 8.41 ms
    Out[98]: 0.6746549805785002
    """
    if a.shape != b.shape:
        raise ValueError(f"Array shapes do not match: {a.shape} != {b.shape}")

    a = a.astype(np.float32)
    b = b.astype(np.float32)

    # Compute the normalized cross-correlation
    return np.sum(a * b) / (np.sqrt(np.sum(a ** 2)) * np.sqrt(np.sum(b ** 2)))


class SongFinder:
    """
    Finds a song from the screen based on cover image similarity
    """
    cover_hashes: dict[str, ImageHash]
    music_data: dict[int, dict]

    def __init__(self):
        # Load cover hashes from picle
        with (Path(__file__).parent / 'data/cover_hashes.pkl').open('rb') as f:
            self.cover_hashes = pickle.load(f)
        # Load music data
        self.music_data = {it['id']: it for it in json.loads(
            (Path(__file__).parent / 'data/musics.json').read_text())}

    def find(self, cover: ndarray) -> tuple[int, dict]:
        # Covert to PIL image
        cover_hash = imagehash.phash(Image.fromarray(cv2.resize(cover, (740, 740))))
        # Find the lowest hash distance
        hashes = list(self.cover_hashes.items())
        scores = [cover_hash - hsh for _, hsh in hashes]
        best = np.argmin(scores)
        id = int(hashes[best][0])
        print(f"> Song finder best match: ID {id} - Score {scores[best]}")
        return id, self.music_data[id]


class ImageFinder:
    """
    This is an instance of an image UI element at a specific screen location. The raw files are saved
    by `editor.py` which contains a rect bounding box for the UI element and a crop image. You can use this
    to find whether the element is on screen.
    """
    name: str
    start: tuple[int, int]
    end: tuple[int, int]
    center: tuple[int, int]
    offset: tuple[int, int]
    crop: ndarray
    gray: ndarray

    def __init__(self, name: str):
        # Load the image finder data from the editor by directory name
        self.name = name
        p = Path(__file__).parent / 'stages/editor' / name
        if not p.is_dir():
            raise FileNotFoundError(f"Image finder {name} not found")

        # Load the metadata
        with (p / 'meta.toml').open() as f:
            meta = toml.load(f)
            self.start = meta['start']
            self.end = meta['end']
            self.offset = meta.get('offset', (0, 0))
            # Add one pixel to the start point
            # (because the editor accidentally drew the rectangle box on the crop line)
            self.start = (self.start[0] + 1, self.start[1] + 1)

            self.center = (self.start[0] + (self.end[0] - self.start[0]) // 2 + self.offset[0],
                           self.start[1] + (self.end[1] - self.start[1]) // 2 + self.offset[1])

        # Load the crop image (remove 1px border)
        self.crop = cv2.imread(str(p / 'crop.png'))[1:, 1:]
        self.gray = cv2.cvtColor(self.crop, cv2.COLOR_BGR2GRAY)

    def get_region(self, frame: ndarray) -> ndarray:
        """
        Crop the UI element from the screen frame

        :param frame: The screen frame
        :return: The cropped UI element
        """
        return frame[self.start[1]:self.end[1], self.start[0]:self.end[0]]

    def check(self, frame: ndarray) -> tuple[int, int] | None:
        """
        Check whether the UI element is on the screen

        :param frame: The screen frame (grayscale)
        :return: The center position (including offset) when found, None otherwise
        """
        region = self.get_region(frame)

        # Check if frame is grayscale
        if len(region.shape) == 3:
            region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        assert region.shape == self.gray.shape, f"Region shape mismatch: {region.shape} != {self.gray.shape}"

        # Check similarity
        res = max(cv2.matchTemplate(region, self.gray, cv2.TM_CCOEFF_NORMED).flatten())
        if res > config.image_threshold:
            return self.center


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
    t = time.time()
    result = cv2.matchTemplate(source, wanted, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    print(f"Match time: {time.time() - t:.3f}s")

    if max_val >= accuracy:
        # Debug: Draw the bounding rect of the found image
        if config.debug:
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


if __name__ == '__main__':
    # Test album finder
    finder = SongFinder()
    crop = cv2.imread('stages/editor/song_cover/crop.png')
    print(finder.find(crop))
