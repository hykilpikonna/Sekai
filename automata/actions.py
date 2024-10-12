from uuid import uuid4

import scrcpy

from .models import Action, SekaiStageContext


class ATap(Action):
    """
    An action that taps on a certain coordinate
    """
    def __init__(self, x: int, y: int, touch_id: int = 0, action: int = -1):
        self.x = x
        self.y = y
        self.touch_id = touch_id
        self.action = action

    def start(self, ctx: SekaiStageContext):
        # Tap
        if self.action == -1:
            ctx.client.control.touch(self.x, self.y, scrcpy.ACTION_DOWN, self.touch_id)
            ctx.client.control.touch(self.x, self.y, scrcpy.ACTION_UP, self.touch_id)
        else:
            ctx.client.control.touch(self.x, self.y, self.action, self.touch_id)
        return True


class ABack(Action):
    """
    An action that presses the back button
    """
    def start(self, ctx: SekaiStageContext):
        ctx.client.control.back_or_turn_screen_on(scrcpy.ACTION_DOWN)
        ctx.client.control.back_or_turn_screen_on(scrcpy.ACTION_UP)
        return True


class ADelay(Action):
    """
    An action that waits for a certain amount of time before completing

    :param delay: The delay in seconds
    """
    def __init__(self, delay: float):
        self.delay = delay
        self.uuid = uuid4()

    def start(self, ctx: SekaiStageContext):
        ctx.store[self.uuid] = ctx.time + self.delay * 1_000  # Convert to milliseconds

    def update(self, ctx: SekaiStageContext):
        if ctx.time >= ctx.store[self.uuid]:
            del ctx.store[self.uuid]
            return True

