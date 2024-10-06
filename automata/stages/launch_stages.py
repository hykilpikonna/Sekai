import json
import time
from pathlib import Path

import cv2
import numpy as np

from ..actions import ATap, ADelay
from ..config import log, config, global_dict
from ..gamer import SekaiGamer
from ..models import SekaiStage, SekaiStageContext, SekaiStageOp
from ..util import ImageFinder, SongFinder


class MatchAndClick(SekaiStage):
    images: dict[str, ImageFinder]

    def __init__(self):
        super().__init__("match_and_click")
        # Load images
        self.images = {it: ImageFinder(it) for it in [
            # Buttons for the song result screen
            'result_first', 'result_first_mp',
            'result_next', 'result_back',
            # When on desktop, in the start menu, etc
            'launch_desktop_icon', 'launch_start',
            # Announcement close button
            'home_announcement_detect',
            # Difficulty select
            'master_not_selected',
            # Home live button (TODO: Make choosing between solo and multi a config option)
            'home_live_solo',
            # 'home_live_multi',
            # Single-player related
            'solo_start', 'solo_start_play',
            # Multiplayer related
            'mp_disconnect', 'mp_ready', 'mp_veteran',
            # mp_select will select your specified song, while mp_omakase will leave it to other players
            'mp_select',
            # 'mp_omakase'
        ]}

    def is_stage(self, ctx: SekaiStageContext) -> bool:
        # Match images
        for name, image in self.images.items():
            pos = image.check(ctx.frame_gray)
            if pos:
                ctx.cache['match-name'] = name
                ctx.cache['match-pos'] = pos
                if 'mp_matching_since' in ctx.store:
                    del ctx.store['mp_matching_since']
                return True

    def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
        # Get the image
        name = ctx.cache['match-name']
        pos = ctx.cache['match-pos']

        # Special case when name = 'solo_start_play': switch to song playing mode
        exp = set()
        if name == 'solo_start_play':
            exp.add('song_start')

        ac = [ATap(*pos)]
        if name.startswith('result_first'):
            # This stage often gets stuck, we need to click multiple times on different positions
            ac = []
            for i in range(6):
                dx, dy, dt = np.random.randint(-50, 50), np.random.randint(-50, 50), np.random.uniform(0.01, 0.3)
                ac.append(ADelay(dt))
                ac.append(ATap(pos[0] + dx, pos[1] + dy))

        # Click the image
        return SekaiStageOp(f"click {name}", ac, exp)


# When it's matching, we don't want to click anything and we also don't want to time out
# So we just wait until the matching is done
class SWaitMPMatching(SekaiStage):
    img: ImageFinder
    back: ImageFinder

    def __init__(self):
        super().__init__("wait_mp_matching")
        self.img = ImageFinder('mp_matching')
        self.back = ImageFinder('mp_back')

    def is_stage(self, ctx: SekaiStageContext) -> bool:
        if self.img.check(ctx.frame_gray):
            if 'mp_matching_since' not in ctx.store:
                ctx.store['mp_matching_since'] = time.time()
            return True

    def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
        # If we waited longer than 30 seconds, click back and try again
        if time.time() - ctx.store['mp_matching_since'] > 30:
            log.error("MP matching timed out")
            del ctx.store['mp_matching_since']
            return SekaiStageOp("mp_back", [ATap(*self.back.center)], set())
        return SekaiStageOp("wait_mp_matching", [ADelay(1)], set())


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
        return SekaiStageOp("song_start", [ADelay(0.8)], {'song_start_next'})


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
        notes = json.loads(p.read_text())

        log.info(f"> Song start: {song['title']} ({d})")
        global_dict['playing'] = SekaiGamer(ctx.client, notes)

        return SekaiStageOp("song_start", [ADelay(0.01)], set())


if __name__ == '__main__':
    img = cv2.imread(r'C:\ws\Sekai\Code\stages\editor\test\crop.png')[1:, 1:]
    print(find_difficulty(img))
