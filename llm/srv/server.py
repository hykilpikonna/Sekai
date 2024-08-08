import argparse
import uuid
from pathlib import Path

import rapidfuzz.process
import uvicorn
from fastapi import HTTPException
from hypy_utils import ensure_dir, write_json
from hypy_utils.logging_utils import setup_logger
from pydantic import BaseModel, Field
from transformers import XLMRobertaTokenizer, XLMRobertaForSequenceClassification

# We do need to set up logger before importing MLC, see https://github.com/mlc-ai/mlc-llm/issues/2780
log = setup_logger()

from server_share import app
from backends.mlc_backend import LLM


src = Path(__file__).parent
data = src / '../data'
# Directory to store session data
db_dir = ensure_dir(src / "database")
# Face and animation model
face_model = '/d/sekai/cls/model/face_data_major_classes'
animations = {v for v in (data / 'animations.txt').read_text('utf-8').splitlines() if v}
faces = {v for v in (data / 'face.txt').read_text('utf-8').splitlines() if v}


class FaceClassifier:
    """
    Classify live2d face id from textual data
    """
    def __init__(self):
        self.tokenizer = XLMRobertaTokenizer.from_pretrained(face_model)
        self.model = XLMRobertaForSequenceClassification.from_pretrained(face_model)

    def classify(self, text: str) -> str:
        inputs = self.tokenizer(text, return_tensors="pt")
        outputs = self.model(**inputs)
        logits = outputs.logits
        predicted_class_id = logits.argmax().item()
        ans = self.model.config.id2label[predicted_class_id]

        # Add face_
        ans = f'face_{ans}'

        # Get the list of valid faces that start with ans
        lst = [face for face in faces if face.startswith(ans)]
        if lst:
            return sorted(lst)[0]

        # Not found, fuzzy match
        return rapidfuzz.process.extractOne(ans, faces, scorer=rapidfuzz.fuzz.QRatio)[0]


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
    for entry in history:
        # animation = f' {{"animation": "{log.animation}", "face": "{log.face}"}}' if log.animation else ""
        prompt += f"""
<|im_start|>{entry.speaker}
{entry.text}<|im_end|>"""

    return prompt


async def gen_response(history: list[ChatLog], force_speaker: str | None = None) -> list[ChatLog]:
    """
    Generate a response given the history and user input
    """
    history = list(history)
    prompt = build_prompt(history)
    log.info(f"IN < {prompt}")

    if force_speaker:
        prompt += f"""\n<|im_start|>{force_speaker}"""
    resp = (await llm.gen(prompt)).strip()
    log.debug(f"OUT > {force_speaker or ''} {resp}")

    # TODO: Identify animation using the classification model
    anim = 'w-cute01-tilthead'

    # Create response
    if not force_speaker and '\n' not in resp:
        log.error(f"Response did not include a newline: {resp}")
        resp = f'？？？\n{resp}'
    speaker, text = (force_speaker, resp) if force_speaker else resp.split('\n', 1)
    face = fc.classify(text)
    result = [ChatLog(
        speaker=speaker, text=text,
        animation=anim, face=face,
        display_text=f"${{anim:{anim}}}${{face:{face}}}${{title:{speaker}}}{text}"
    )]

    # See if it has anything else to say (maximum 3 additional lines)
    target = speaker
    for _ in range(3):
        # Add result to history and generate again to see if it has anything else to say
        history.append(result[-1])
        resp = (await llm.gen(build_prompt(history))).strip()
        log.debug(resp)

        # If the generated speaker is not the same as the previous speaker,
        # then we can stop here
        if '\n' not in resp:
            log.error(f"Response did not include a newline: {resp}")
            resp = f'？？？\n{resp}'
        speaker, text = resp.split('\n', 1)
        if speaker != target:
            break

        # Add the response to the result
        face = fc.classify(text)
        result.append(ChatLog(
            speaker=speaker, text=text,
            animation=anim, face=face,
            display_text=f"${{anim:{anim}}}${{face:{face}}}${{title:{speaker}}}{text}"
        ))

    return result


@app.post("/llm/create")
async def create_session(request: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    session_data = SavedSession(
        name=request.name,
        user_speaker=request.intro.speaker,
        history=[request.intro]
    )
    resp = await gen_response(session_data.history, force_speaker=request.force_speaker)
    session_data.history += resp
    write_json(db_dir / f"{session_id}.json", session_data)
    return {
        "id": session_id,
        "next": resp
    }


@app.post("/llm/gen")
async def generate_response(request: GenerateResponseRequest):
    sf = db_dir / f"{request.id}.json"
    if not sf.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = SavedSession.parse_file(sf)

    session_data.history.append(ChatLog(speaker=session_data.user_speaker, text=request.text, animation=None, face=None))
    resp = await gen_response(session_data.history, force_speaker=request.force_speaker)
    session_data.history += resp

    write_json(sf, session_data)
    return resp


@app.post("/llm/history")
async def get_history(request: GetHistoryRequest) -> list[ChatLog]:
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
async def get_templates():
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
async def health():
    return {"status": "ok"}


if __name__ == '__main__':
    agupa = argparse.ArgumentParser()
    agupa.add_argument("--host", default="0.0.0.0")
    agupa.add_argument("--port", type=int, default=27518)
    agupa.add_argument('action', nargs='?', choices=['run', 'test'], default='run')
    args = agupa.parse_args()

    # Load model and tokenizer
    llm = LLM()
    fc = FaceClassifier()

    if args.action == 'test':
        # Time 10 responses
        import time
        start = time.time()
        for _ in range(10):
            _tmp = gen_response([ChatLog(
                speaker="千葉",
                text="瑞希、はじめまして！私はあなたの従妹の千葉です。しばらくの間、ここに滞在します。よろしくお願いします。",
            )])
            log.info(f"{_tmp[0].text}")

        log.warning(f"Time taken: {(time.time() - start) / 10:.2f}s per response")
    else:
        uvicorn.run(app, host=args.host, port=args.port)
