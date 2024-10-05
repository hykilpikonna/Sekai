"""
This script is used to evaluate the starting response speaker accuracy, which hopefully is an important metric.

What this means is, it
* tries to complete a chat dialog using the model, starting with someone asking a specific character to speak
* generates many responses using different random seeds
* checks how many responded with the correct speaker
"""
import argparse
import random
import time
from pathlib import Path
from tqdm.auto import tqdm
tqdm.pandas()

import pandas as pd
from hypy_utils.logging_utils import setup_logger
from mlc_llm import MLCEngine
from mlc_llm.serve import EngineConfig

log = setup_logger()


def build_prompt(speaker: str, text: str) -> str:
    return f"""
<|im_start|>system
プロセカのメンバー間の会話のダイアログを書いてください。繰り返しを避けてください。<|im_end|>
<|im_start|>{speaker}
{text}<|im_end|>"""


class DS4Models:
    engine: MLCEngine
    start = "<|im_start|>"
    end = "<|im_end|>"

    def __init__(self, path):
        self.engine = MLCEngine(
            path,
            mode="server",
            engine_config=EngineConfig(
                tensor_parallel_shards=1
            )
        )

    def gen(self, text: str) -> str:
        return (self.engine.completions.create(
            prompt=text, max_tokens=64, temperature=0.9, top_p=0.9, stop=self.end
            # top_k=10,
            # repetition_penalty=1.2
        )).choices[0].text.strip().strip(self.start).strip(self.end)


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
    
    # Random shuffle
    pairs = pairs.sample(frac=1).reset_index(drop=True)

    # Generate responses
    # pairs['response'] = pairs.prompt.apply(lambda x: model.gen(x))
    pairs['response'] = pairs.prompt.progress_apply(lambda x: model.gen(x))

    Path(data / 'eval/resp').mkdir(parents=True, exist_ok=True)

    # Save
    pairs.to_csv(data / f'eval/resp/{mp.stem}.csv', index=False)

