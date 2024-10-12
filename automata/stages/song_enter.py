import json
from pathlib import Path

import cv2
import numpy as np

from ..actions import ADelay
from ..config import log, config, global_dict
from ..gamer import SekaiGamer
from ..models import SekaiStage, SekaiStageContext, SekaiStageOp
from ..util import ImageFinder, SongFinder

difficulties = {
    'master': (204, 51, 255),
    'expert': (255, 68, 119),
    'hard': (255, 204, 0),
    'normal': (51, 204, 255),
    'easy': (17, 221, 119)
}


def find_difficulty(difficulty_img: np.ndarray) -> str:
    # Get the average color
    avg_color = np.mean(difficulty_img[:, 0], axis=0)
    # Convert bgr to rgb
    avg_color = avg_color[[2, 1, 0]]
    diffs = difficulties.items()
    arr = np.array([color for _, color in diffs])
    dist = np.linalg.norm(arr - avg_color, axis=1)
    idx = np.argmin(dist)
    return list(diffs)[idx][0]


class SongStart(SekaiStage):
    song_start_if: ImageFinder

    def __init__(self):
        super().__init__("song_start")
        self.song_start_if = ImageFinder('song_start')

    def is_stage(self, ctx: SekaiStageContext) -> bool:
        return bool(self.song_start_if.check(ctx.frame_gray))

    def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
        # Pass a delay to ensure the song starts
        ctx.store['song_start_next'] = True
        return SekaiStageOp("song_start", [ADelay(0.6)], {'song_start_next'})


class SongStartNext(SekaiStage):
    song_cover_if: ImageFinder
    song_difficulty_if: ImageFinder
    song_finder: SongFinder

    def __init__(self):
        super().__init__("song_start_next")
        self.song_cover_if = ImageFinder('song_cover')
        self.song_difficulty_if = ImageFinder('song_difficulty')
        self.song_finder = SongFinder()

    def is_stage(self, ctx: SekaiStageContext) -> bool:
        return ctx.store.get('song_start_next', False)

    def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
        del ctx.store['song_start_next']
        # Get the song cover
        cover = self.song_cover_if.get_region(ctx.frame)
        song_id, song = self.song_finder.find(cover)

        # Check the difficulty using color similarity
        diff = self.song_difficulty_if.get_region(ctx.frame)
        d = find_difficulty(diff)

        # Load notes
        p = Path(config.music_path.replace('{ID}', str(song_id).zfill(3))) / f'{d}.json'
        if not p.exists():
            log.error(f"Notes not found: {p}")
            return SekaiStageOp("song_start", [ADelay(0.01)], set())
        notes = json.loads(p.read_text('utf-8'))

        log.info(f"> Song start: {song['title']} ({d})")
        global_dict['playing'] = SekaiGamer(ctx.client, notes)

        return SekaiStageOp("song_start", [ADelay(0.01)], set())


if __name__ == '__main__':
    img = cv2.imread(r'C:\ws\Sekai\Code\stages\editor\test\crop.png')[1:, 1:]
    print(find_difficulty(img))