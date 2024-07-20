import argparse
import json
import uuid
from pathlib import Path

import rapidfuzz.process
import torch
import uvicorn
from fastapi import HTTPException
from hypy_utils import ensure_dir, write_json
from hypy_utils.logging_utils import setup_logger
from pydantic import BaseModel, Field
from server_share import app
import server_misc
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path = "/mnt/data/menci/llm/export/ds4-instruct-1"
log = setup_logger()

# Directory to store session data
db_dir = ensure_dir(Path(__file__).parent / "database")
animations = {v for v in (Path(__file__).parent / 'animations.txt').read_text('utf-8').splitlines() if v}


class LLM:
    dev: str = "cuda:0" if torch.cuda.is_available() else "cpu"
    m: AutoModelForCausalLM
    t: AutoTokenizer
    start = "<|im_start|>"
    end = "<|im_end|>"
    params: dict

    def __init__(self):
        # Load models
        self.m = AutoModelForCausalLM.from_pretrained(
            # m = AutoGPTQForCausalLM.from_quantized(
            model_path, torch_dtype=torch.float16, device_map="auto",
            attn_implementation="flash_attention_2"
        ).to(self.dev)
        self.t = AutoTokenizer.from_pretrained(model_path)
        self.params = {
            # "eos_token_id": self.t.eos_token_id,
            "pad_token_id": self.t.pad_token_id,
            "max_new_tokens": 64,
            "temperature": 0.9,
            # "top_p": 0.9,
            # "top_k": 50,
            # "repetition_penalty": 1.2
        }

    def gen(self, prompt: str) -> str:
        model_inputs = self.t(prompt, return_tensors="pt").to(self.dev)
        return self.t.decode(self.m.generate(**model_inputs, **self.params)[0], skip_special_tokens=False)



class GenerateResponseRequest(BaseModel):
    id: str
    text: str
    force_speaker: str | None = Field(default=None)


class ChatLog(BaseModel):
    speaker: str
    text: str
    animation: str | None = Field(default=None)
    face: str | None = Field(default=None)
    display_text: str | None = Field(default=None)


class CreateSessionRequest(BaseModel):
    name: str
    intro: ChatLog
    force_speaker: str | None = Field(default=None)


class SavedSession(BaseModel):
    name: str
    user_speaker: str
    history: list[ChatLog]


class GetHistoryRequest(BaseModel):
    id: str


def build_prompt(history: list[ChatLog]) -> str:
    """
    Build prompt from historical chat log
    """
    prompt = f"""
<|im_start|>system
プロセカのメンバー間の会話のダイアログを書いてください。繰り返しを避けてください。<|im_end|>""".strip()
    for log in history:
        # animation = f' {{"animation": "{log.animation}", "face": "{log.face}"}}' if log.animation else ""
        prompt += f"""
<|im_start|>{log.speaker}
{log.text}<|im_end|>"""

    return prompt


def gen_response(history: list[ChatLog], force_speaker: str | None = None) -> list[ChatLog]:
    """
    Generate a response given the history and user input
    """
    prompt = build_prompt(history)
    log.debug(prompt)

    tmp = prompt
    if force_speaker:
        tmp += f"""\n<|im_start|>{force_speaker}"""
    resp = llm.gen(tmp)
    log.debug(resp)

    # Remove input text from response
    resp = resp[len(prompt):].strip()

    # Loop through the response and parse each <|im_start|>...<|im_end|>
    result = []
    user_speaker = history[-1].speaker
    while llm.start in resp and llm.end in resp:
        # Find the start
        resp = resp[resp.index(llm.start) + len(llm.start):]

        # Find the end
        segment = resp[:resp.index(llm.end)]
        resp = resp[len(segment) + len(llm.end):].strip()

        # Parse the segment
        spl = segment.split('\n', 1)
        speaker = spl[0].strip()
        text = spl[1].strip()

        # If LLM starts to imagine the text of the user, then we can stop here
        if speaker == user_speaker or speaker == 'system':
            break

        # TODO: Classify animation using the classification model
        animation = "w-cute01-tilthead"
        face = "face_smile_01"

        # Add the segment to the result
        result.append(ChatLog(
            speaker=speaker, text=text,
            animation=animation, face=face,
            display_text=f"${{anim:{animation}}}${{face:{face}}}${{title:{speaker}}}{text}"
        ))

    return result


@app.post("/llm/create")
def create_session(request: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    session_data = SavedSession(
        name=request.name,
        user_speaker=request.intro.speaker,
        history=[request.intro]
    )
    resp = gen_response(session_data.history, force_speaker=request.force_speaker)
    session_data.history += resp
    write_json(db_dir / f"{session_id}.json", session_data)
    return {
        "id": session_id,
        "next": resp
    }


@app.post("/llm/gen")
def generate_response(request: GenerateResponseRequest):
    sf = db_dir / f"{request.id}.json"
    if not sf.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = SavedSession.parse_file(sf)

    session_data.history.append(ChatLog(speaker=session_data.user_speaker, text=request.text, animation=None, face=None))
    resp = gen_response(session_data.history, force_speaker=request.force_speaker)
    session_data.history += resp

    write_json(sf, session_data)
    return resp


@app.post("/llm/history")
def get_history(request: GetHistoryRequest) -> list[ChatLog]:
    """
    Get the history of a session
    :return: List of chat logs
    """
    sf = db_dir / f"{request.id}.json"
    if not sf.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = SavedSession.parse_file(sf)
    return session_data.history


@app.get("/llm/templates")
def get_templates():
    """
    Get a list of conversation starting prompt templates for the LLM.
    They are roles that the user can take.
    """
    return {
        "templates": [
            {
                "log": ChatLog(
                    speaker="千葉",
                    text="瑞希さん、おはよう！私はあなたの従妹の千葉です。しばらくの間、ここに滞在します。よろしくお願いします。"
                ),
                "description": "瑞希の従妹の千葉として会話を始める。"
            },
            {
                "log": ChatLog(
                    speaker="彩花",
                    text="こんにちは、暁山さん！はじめまして。いつもニーゴの音楽聴いてるよ。会えて本当に嬉しい！"
                ),
                "description": "瑞希ファンの彩花"
            },
        ]
    }


@app.get('/llm/health')
def health():
    return {"status": "ok"}


if __name__ == '__main__':
    agupa = argparse.ArgumentParser()
    agupa.add_argument("--host", default="0.0.0.0")
    agupa.add_argument("--port", type=int, default=27518)
    agupa.add_argument('action', nargs='?', choices=['run', 'test'], default='run')
    args = agupa.parse_args()

    # Load model and tokenizer
    llm = LLM()

    if args.action == 'test':
        # Time 10 responses
        import time
        start = time.time()
        for _ in range(10):
            resp = gen_response([ChatLog(
                speaker="千葉",
                text="瑞希、はじめまして！私はあなたの従妹の千葉です。しばらくの間、ここに滞在します。よろしくお願いします。",
            )])
            print(resp.speaker, ":", resp.text)

        print(f"Time taken: {(time.time() - start) / 10:.2f}s per response")
    else:
        uvicorn.run(app, host=args.host, port=args.port)
