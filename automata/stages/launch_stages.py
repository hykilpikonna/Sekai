from ..actions import ATap
from ..models import SekaiStage, SekaiStageContext, SekaiStageOp
from ..util import ImageFinder


class MatchAndClick(SekaiStage):
    images: dict[str, ImageFinder]

    def __init__(self):
        super().__init__("match_and_click")
        # Load images
        self.images = {it: ImageFinder(it) for it in [
            # Buttons for the song result screen
            'result_first', 'result_next', 'result_back',
            # When on desktop, in the start menu, etc
            'launch_desktop_icon', 'launch_start',
            # Announcement close button
            'home_announcement_detect',
            # Home live solo button (TODO: Implement multiplayer
            'home_live_solo', 'solo_start', 'solo_start_play'
        ]}

    def is_stage(self, ctx: SekaiStageContext) -> bool:
        # Match images
        for name, image in self.images.items():
            pos = image.check(ctx.frame_gray)
            if pos:
                ctx.cache['match-name'] = name
                ctx.cache['match-pos'] = pos
                return True

    def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
        # Get the image
        name = ctx.cache['match-name']
        pos = ctx.cache['match-pos']

        # Special case when name = 'solo_start_play': switch to song playing mode
        # TODO

        # Click the image
        return SekaiStageOp(f"click {name}", [ATap(*pos)], set())
