import time

from lmdeploy import pipeline, GenerationConfig, TurbomindEngineConfig


class LLM:
    """
    Powered by LMDeploy
    """
    pipe: pipeline
    start = "<|im_start|>"
    end = "<|im_end|>"

    def __init__(self):
        config = TurbomindEngineConfig(tp=1, session_len=1024)
        self.pipe = pipeline("/d/sekai/llm/export/ds4-instruct-1-awq4", backend_config=config)

    def gen(self, text: str) -> str:
        return self.pipe(text, gen_config=GenerationConfig(
            max_new_tokens=64,
            temperature=0.9,
            repetition_penalty=1.2,  # This is extremely important!
            random_seed=time.time_ns() % 2**32,
            top_k=10,
            top_p=0.9
        )).text