import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import scrcpy
from numpy import ndarray


class Action(ABC):
    started: bool = False

    def run(self, ctx: 'SekaiStageContext') -> bool | None:
        if not self.started:
            self.started = True
            return self.start(ctx)
        return self.update(ctx)

    @abstractmethod
    def start(self, ctx: 'SekaiStageContext') -> bool | None:
        """
        Start the action

        :param ctx: The context object
        :return: True if the action ixxxxxs completed, False or None otherwise
        """
        pass

    def update(self, ctx: 'SekaiStageContext') -> bool | None:
        """
        Called on every frame until the action is completed

        :param ctx: The context object
        :return: True if the action is completed, False or None otherwise
        """
        return True


@dataclass
class SekaiStageOp:
    name: str
    actions: list[Action]
    next_stage: set[str]
    next_stage_timeout: float = 2.0
    action_i: int = 0


@dataclass
class SekaiStageContext:
    client: scrcpy.Client
    frame: ndarray
    cache: dict
    store: dict
    time: int  # Current time in milliseconds when the frame was captured
    last_op: SekaiStageOp
    last_op_done: int | None = 1  # Time when the last operation was completed, if it is completed
    frame_gray: ndarray = None

    def tap(self, x: int, y: int):
        id = random.randint(0, 500)
        self.client.control.touch(x, y, scrcpy.ACTION_DOWN, id)
        self.client.control.touch(x, y, scrcpy.ACTION_UP, id)

    def next(self, frame: ndarray):
        self.cache.clear()
        self.frame = frame
        self.frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.time = time.time_ns() // 1_000_000


class SekaiStage(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def is_stage(self, ctx: SekaiStageContext) -> bool:
        """
        Check if the current frame is the stage that this class represents

        :param ctx: The context object
        :return: True if the current frame is the stage that this class represents
        """
        pass

    @abstractmethod
    def operate(self, ctx: SekaiStageContext) -> SekaiStageOp:
        """
        Perform the actions required for this stage and return the expected next stage

        :param ctx: The context object
        :return: The expected next stage
        """
        pass
