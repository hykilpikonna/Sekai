from abc import ABC, abstractmethod
from uuid import uuid4

import scrcpy

from automata.stage import SekaiStageContext


class Action(ABC):
    @abstractmethod
    def start(self, ctx: SekaiStageContext) -> bool | None:
        """
        Start the action

        :param ctx: The context object
        :return: True if the action is completed, False or None otherwise
        """
        pass

    def update(self, ctx: SekaiStageContext) -> bool | None:
        """
        Called on every frame until the action is completed

        :param ctx: The context object
        :return: True if the action is completed, False or None otherwise
        """
        pass

    def end(self, ctx: SekaiStageContext):
        """
        Called when the action is completed

        :param ctx: The context object
        """
        pass


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


class ADelay(Action):
    """
    An action that waits for a certain amount of time before completing

    :param delay: The delay in seconds
    """
    def __init__(self, delay: float):
        self.delay = delay
        self.uuid = uuid4()

    def start(self, ctx: SekaiStageContext):
        ctx.storage[self.uuid] = ctx.time + self.delay * 1_000  # Convert to milliseconds

    def update(self, ctx: SekaiStageContext):
        if ctx.time >= ctx.storage[self.uuid]:
            return True

