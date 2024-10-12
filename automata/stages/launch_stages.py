import time

import requests

from ..actions import ATap, ADelay
from ..config import log, HOST_ADDR, get_mode
from ..models import SekaiStage, SekaiStageContext, SekaiStageOp
from ..util import ImageFinder


class MatchAndClick(SekaiStage):
    images: dict[str, ImageFinder]

    def __init__(self):
        super().__init__("050_match_and_click")
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
            # 'home_live_solo',
            'home_live_multi',
            # Single-player related
            'solo_start', 'solo_start_play',
            # Multiplayer related
            'mp_disconnect', 'mp_ready', 
            # Create multiplayer room if you're solo or a host
            {'self': 'mp_create', 'host': 'mp_create_free', 'helper': 'bmp_enter'}[get_mode()],
            'mp_create_confirm', 'mp_create_open_confirm', 'mp_create_again', 'result_mp_ok',
            *(['mp_create_open'] if get_mode() == 'self' else []),
            # mp_select will select your specified song, while mp_omakase will leave it to other players
            'mp_select' if get_mode() == 'host' else 'mp_omakase',
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
            exp = {'song_start'}
        if name.startswith('mp_create_confirm'):
            exp = {'0_match_and_click'}

        ac = [ATap(*pos)]

        # Save a screenshot on result
        if name.startswith('result'):
            ctx.save()

        # Click the image
        return SekaiStageOp(f"click {name}", ac, exp)


# Wait for host to start the game
if get_mode() == 'helper':
    class BMPHelperEnter(SekaiStage):
        keys: list[ImageFinder]
        confirm: ImageFinder

        def __init__(self):
            super().__init__("bmp_enter")
            self.keys = [ImageFinder(f'bmp_enter_id/{i}') for i in range(0, 10)]
            self.confirm = ImageFinder('bmp_enter_confirm')

        def is_stage(self, ctx: SekaiStageContext) -> bool:
            return bool(self.keys[0].check(ctx.frame_gray))

        def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
            # Get the room ID from the host
            resp = {}
            try:
                resp = requests.get(f'{HOST_ADDR}/bmp_room_id').json()
            except requests.RequestException as e:
                log.error(f"Failed to get room ID: {e}")
            if not resp.get('id'):
                return SekaiStageOp("BMP: Wait for host", [ADelay(1)], {"bmp_enter"})

            ctx.store['room_id'] = resp['id']

            # Enter the room ID
            ops = [ATap(*self.keys[int(i)].center) for i in str(resp['id'])]
            ops.append(ATap(*self.confirm.center))
            # After each key, add a short 100ms delay
            ops = [op for op in ops for op in [op, ADelay(0.1)]]
            return SekaiStageOp("BMP: Enter room key", ops, {"bmp_enter"})


# Wait for matching players to join
if get_mode() != 'self':
    class BMPMatching(SekaiStage):
        img: ImageFinder
        waits: list[ImageFinder]
        back: ImageFinder
        launch: ImageFinder

        def __init__(self):
            super().__init__("002_wait_mp_matching")
            self.img = ImageFinder('bmp_invite')
            self.waits = [ImageFinder(f'bmp_wait_p{i}') for i in range(2, 6)]
            self.back = ImageFinder('mp_back')
            self.launch = ImageFinder('bmp_launch')

        def is_stage(self, ctx: SekaiStageContext) -> bool:
            if self.img.check(ctx.frame_gray):
                if 'mp_matching_since' not in ctx.store:
                    ctx.store['mp_matching_since'] = time.time()
                return True

        def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
            # If we waited longer than 3 minutes, click back and try again
            # if time.time() - ctx.store['mp_matching_since'] > 3 * 60:
            #     log.error("MP matching timed out")
            #     del ctx.store['mp_matching_since']
            #     return SekaiStageOp("mp_back", [ATap(*self.back.center)], set())

            # If I'm the helper but I've been granted the host, it means that the host has quit
            # So I should quit and wait for the host to start again
            if get_mode() == 'helper' and self.launch.check(ctx.frame_gray):
                return SekaiStageOp("BMP: The host has quit so I quit too", [ATap(*self.back.center)], set())

            return SekaiStageOp("BMP: Waiting", [ADelay(1)], {"wait_mp_matching", "0_match_and_click"})


# When it's matching, we don't want to click anything and we also don't want to time out
# So we just wait until the matching is done
if get_mode() == 'self':
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
            return SekaiStageOp("wait_mp_matching", [ADelay(1)], {"wait_mp_matching", "0_match_and_click"})
