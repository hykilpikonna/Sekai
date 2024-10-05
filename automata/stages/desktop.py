from ..actions import ATap, ADelay
from ..stage import SekaiStage, SekaiStageOp
from ..util import img, locate


class SDesktop(SekaiStage):
    """
    The android desktop. Somehow the game have crashed. We will try to restart it.
    """
    icon = img("desktop-icon.png")

    def __init__(self):
        super().__init__("desktop")

    def is_stage(self, ctx) -> bool:
        coord = locate(ctx.frame, self.icon)
        if coord:
            ctx.storage["icon"] = coord
            return True

    def operate(self, ctx) -> SekaiStageOp:
        # Click the desktop icon
        x, y = ctx.storage["icon"]
        return SekaiStageOp([
            ATap(x, y),
            ADelay(1)
        ], "main_menu", next_stage_timeout=60)
