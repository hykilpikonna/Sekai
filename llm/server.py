import argparse
import json
import os
from typing import Optional
import uuid
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from hypy_utils import ensure_dir, write_json
from hypy_utils.logging_utils import setup_logger
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

app = FastAPI()
device = "cuda:0" if torch.cuda.is_available() else "cpu"
model_path = "/mnt/data/menci/llm/export"
log = setup_logger()

# Directory to store session data
db_dir = ensure_dir(Path(__file__).parent / "database")


class GenerateResponseRequest(BaseModel):
    id: str
    text: str


class ChatLog(BaseModel):
    speaker: str
    text: str
    animation: str | None
    face: str | None
    display_text: str | None = Field(default=None)


class CreateSessionRequest(BaseModel):
    name: str
    intro: ChatLog


class SavedSession(BaseModel):
    name: str
    user_speaker: str
    history: list[ChatLog]


def build_prompt(history: list[ChatLog]) -> str:
    """
    Build prompt from historical chat log
    """
    prompt = """
<|im_start|>system
リアルなテキストメッセージのやり取りを書いてください。繰り返しを避けてください。<|im_end|>""".strip()
    for log in history:
        animation = f' {{"animation": "{log.animation}", "face": "{log.face}"}}' if log.animation else ""
        prompt += f"""
<|im_start|>{log.speaker}{animation}
{log.text}<|im_end|>"""

    return prompt


def gen_response(history: list[ChatLog]) -> ChatLog:
    """
    Generate a response given the history and user input
    """
    prompt = build_prompt(history)
    log.debug(prompt)
    model_inputs = tokenizer(prompt, return_tensors="pt").to(device)

    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=128,
        eos_token_id=tokenizer.eos_token_id
    )

    response_text = tokenizer.decode(generated_ids[0], skip_special_tokens=False)
    log.debug(response_text)

    # Parse speaker, animation, and face from the response text
    response_text = response_text.rsplit("<|im_start|>", 1)[-1].replace("<|im_end|>", "")
    lines = response_text.splitlines()
    idx = lines[0].index('{')
    if idx > 0:
        speaker = lines[0][:idx]
        jsn = json.loads(lines[0][idx:])
        face, animation = jsn['face'], jsn['animation']
        try:
            a1, a2, a3 = animation.split("_")
            animation = f"w-{a1}-{a2}{a3}"
        except Exception:
            pass
    else:
        speaker = lines[0]
        face, animation = None, None

    text = '\n'.join(lines[1:])

    return ChatLog(speaker=speaker.strip(), text=text.strip(), animation=animation.strip(), face=face.strip(),
                   display_text=f"${{anim:{animation}}}${{face:face_{face}_01}}${{title:{speaker}}}{text}")


@app.post("/llm/create")
def create_session(request: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    session_data = SavedSession(
        name=request.name,
        user_speaker=request.intro.speaker,
        history=[request.intro]
    )
    session_data.history.append(gen_response(session_data.history))
    write_json(db_dir / f"{session_id}.json", session_data)
    return {
        "id": session_id,
        "next": session_data.history[-1]
    }


@app.post("/llm/gen")
def generate_response(request: GenerateResponseRequest):
    sf = db_dir / f"{request.id}.json"
    if not sf.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = SavedSession.parse_file(sf)

    session_data.history.append(ChatLog(speaker=session_data.user_speaker, text=request.text, animation=None, face=None))
    session_data.history.append(gen_response(session_data.history))

    write_json(sf, session_data)
    return session_data.history[-1]


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
                    text="瑞希、はじめまして！私はあなたの従妹の千葉です。しばらくの間、ここに滞在します。よろしくお願いします。",
                    animation="cute_tilthead_11",
                    face="smile"
                ),
                "description": "瑞希の従妹の千葉として会話を始める。"
            },
        ]
    }


if __name__ == '__main__':
    agupa = argparse.ArgumentParser()
    agupa.add_argument("--host", default="0.0.0.0")
    agupa.add_argument("--port", type=int, default=27518)
    agupa.add_argument('action', nargs='?', choices=['run', 'test'], default='run')
    args = agupa.parse_args()

    # Load model and tokenizer
    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype="auto", device_map="auto").to(device)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    if args.action == 'test':
        gen_response([ChatLog(
            speaker="千葉",
            text="瑞希、はじめまして！私はあなたの従妹の千葉です。しばらくの間、ここに滞在します。よろしくお願いします。",
            animation="cute_tilthead_11",
            face="smile"
        )])
    else:
        uvicorn.run(app, host=args.host, port=args.port)
