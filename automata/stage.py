"""
这个脚本可以用一张图片来分辨出这个游戏在哪个状态（例如：主界面、选歌界面、游戏界面等等）

Every stage will be a class implementation of the interface SekaiStage, with a method called `is_stage` that will return
True if the current screen is the stage that the class represents, and a method `operate` that will perform the actions
required and return the expected next stage. Also, each stage will have a unique name, which is passed up to the parent
constructor, which will be used to create a dictionary of stages.
"""
import importlib
import logging
from pathlib import Path

from .models import SekaiStage, SekaiStageContext


def load_stages() -> dict[str, SekaiStage]:
    """
    Load all stages

    :return: A dictionary of stages
    """
    # Import each module in "stages" package
    for p in Path(__file__).parent.glob('stages/*.py'):
        importlib.import_module(f'.stages.{p.stem}', package='automata')

    def recursive_subclasses(cls):
        return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in recursive_subclasses(s)]

    sub = recursive_subclasses(SekaiStage)

    # Get all subclasses of SekaiStage
    stages = {cls() for cls in sub if cls.__module__.startswith('automata.stages')}
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

    for stage_name in sorted(expect):
        if stage_name not in stages:
            logging.error(f'[STAGE] Stage {stage_name} is not found in the stages')
            continue
        stage = stages[stage_name]

        if stage.is_stage(ctx):
            return stage

    # Check the remaining stages
    for stage_name in sorted(set(stages.keys()) - set(expect)):
        stage = stages[stage_name]
        if stage.is_stage(ctx):
            if expect:
                logging.warning(f'[STAGE] Stage {stage_name} is not expected. Expected stages are: {expect}')
            return stage
