"""
这个脚本可以用一张图片来分辨出这个游戏在哪个状态（例如：主界面、选歌界面、游戏界面等等）

Every stage will be a class implementation of the interface SekaiStage, with a method called `is_stage` that will return
True if the current screen is the stage that the class represents, and a method `operate` that will perform the actions
required and return the expected next stage. Also, each stage will have a unique name, which is passed up to the parent
constructor, which will be used to create a dictionary of stages.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import scrcpy
from numpy import ndarray

from .actions import Action


@dataclass
class SekaiStageOp:
    actions: list[Action]
    next_stage: str | list[str]
    next_stage_timeout: float = 5.0


@dataclass
class SekaiStageContext:
    client: scrcpy.Client
    frame: ndarray
    storage: dict
    time: int  # Current time in milliseconds when the frame was captured
    last_op: SekaiStageOp | None = None
    last_op_done: bool = False

    def tap(self, x: int, y: int):
        self.client.control.touch(x, y, scrcpy.ACTION_DOWN)
        self.client.control.touch(x, y, scrcpy.ACTION_UP)


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


def load_stages() -> dict[str, SekaiStage]:
    """
    Load all stages

    :return: A dictionary of stages
    """
    # Import each module in "stages" package
    import importlib
    import pkgutil
    import stages

    for loader, module, is_pkg in pkgutil.walk_packages(stages.__path__):
        importlib.import_module(f"stages.{module}")

    # Get all subclasses of SekaiStage
    stages = {cls() for cls in SekaiStage.__subclasses__()}
    return {stage.name: stage for stage in stages}


def find_stage(ctx: SekaiStageContext, stages: dict[str, SekaiStage]) -> SekaiStage | None:
    """
    Find the current stage

    :param ctx: The context object
    :param stages: The dictionary of stages
    :return: The current stage
    """
    # Assume that last_op is done
    assert ctx.last_op_done, "Last operation is not done"

    # Check the expected stage first
    expect = set(ctx.last_op.next_stage) if ctx.last_op else set()

    for stage_name in expect:
        assert stage_name in stages, f"Stage {stage_name} not found"
        stage = stages[stage_name]

        if stage.is_stage(ctx):
            return stage

    # Check the remaining stages
    for stage_name in set(stages.keys()) - expect:
        stage = stages[stage_name]
        if stage.is_stage(ctx):
            logging.warn(f'[STAGE] Stage {stage_name} is not expected. Expected stages are: {expect}')
            return stage
