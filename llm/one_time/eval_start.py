"""
This script is used to evaluate the starting response speaker accuracy, which hopefully is an important metric.

What this means is, it
* tries to complete a chat dialog using the model, starting with someone asking a specific character to speak
* generates many responses using different random seeds
* checks how many responded with the correct speaker
"""
import argparse
import json
import random
import time
from pathlib import Path
from tqdm.auto import tqdm
tqdm.pandas()

import pandas as pd
from hypy_utils.logging_utils import setup_logger
from lmdeploy import pipeline, GenerationConfig, TurbomindEngineConfig

log = setup_logger()


def build_prompt(speaker: str, text: str) -> str:
    return f"""
<|im_start|>system
プロセカのメンバー間の会話のダイアログを書いてください。繰り返しを避けてください。<|im_end|>
<|im_start|>{speaker}
{text}<|im_end|>"""


class DS4Models:
    pipe: pipeline

    def __init__(self, path: str | Path):
        config = TurbomindEngineConfig(tp=2, session_len=1024)
        self.pipe = pipeline(path, backend_config=config)

    def gen(self, text: list[str]) -> list[str]:
        return [v.text for v in self.pipe(text, gen_config=GenerationConfig(
            max_new_tokens=64,
            temperature=0.9,
            repetition_penalty=1.2,  # This is extremely important!
            random_seed=time.time_ns() % 2**32,
            top_k=10,
            top_p=0.9
        ))]


if __name__ == '__main__':
    agupa = argparse.ArgumentParser()
    agupa.add_argument('model', type=str)
    args = agupa.parse_args()
    mp = Path(args.model)

    src = Path(__file__).parent
    data = src.parent / 'data'

    model = DS4Models(str(mp))
    # Has columns: "speaker" and "target"
    pairs = pd.read_csv(data / 'eval/eval_speakers.csv')

    # Generate prompts
    pairs['prompt'] = pairs.apply(lambda x: build_prompt(x.speaker, f'{x.target}、最近どうですか？'), axis=1)

    # Testing: limit to 10 entries first
    # pairs = pairs.sample(10)

    # Random shuffle
    pairs = pairs.sample(frac=1).reset_index(drop=True)

    # Generate responses
    # pairs['response'] = pairs.prompt.apply(lambda x: model.gen(x))
    pairs['response'] = pairs.prompt.progress_apply(lambda x: model.gen([x])[0])
    # pairs['response'] = model.gen(list(pairs.prompt))

    Path(data / 'eval/resp').mkdir(parents=True, exist_ok=True)

    # Save
    pairs.to_csv(data / f'eval/resp/{mp.stem}-lmd-pr-tp2.csv', index=False)

