from mlc_llm import MLCEngine


class LLM:
    """
    Since LMDeploy is not supported on many architectures (e.g. V100), I ported this to MLC LLM even though it probably
    performs worse than LMDeploy.
    """
    engine: MLCEngine
    start = "<|im_start|>"
    end = "<|im_end|>"

    def __init__(self):
        self.engine = MLCEngine("/d/sekai/llm/export/ds4-base-3-q4f16-MLC", mode="server")

    def gen(self, text: str) -> str:
        return self.engine.completions.create(
            prompt=text, max_tokens=64, temperature=0.9, top_p=0.9, stop=self.end
            # top_k=10,
            # repetition_penalty=1.2
        ).choices[0].text
