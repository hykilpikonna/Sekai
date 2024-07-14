from pathlib import Path
import random

from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from server_share import app


BACKGROUND_PATH = Path(__file__).parent / 'backgrounds'
app.mount("/misc/bg", StaticFiles(directory=BACKGROUND_PATH), name="bg")


class BG(BaseModel):
    img: str
    bgm: str


BG_LIST = [
    BG(img="sekai0.png", bgm="sekai0.mp3"),
    BG(img="sekai1.png", bgm="sekai1.mp3"),
    BG(img="bg_e000401.png", bgm="DayHappy.mp3"),
    BG(img="bg_e000402.png", bgm="NightRelax.mp3"),
    BG(img="bg_e000403.png", bgm="RelaxDzDz.mp3"),
    BG(img="bg_e000405.png", bgm="NightRelax.mp3"),
    BG(img="bg_e001701.png", bgm="DayHappy.mp3"),
]
for f in BG_LIST:
    f.img = f"/misc/bg/img/{f.img}"
    f.bgm = f"/misc/bg/bgm/{f.bgm}"


@app.get("/misc/bg")
def rand_bg():
    # Randomly select a background from the list
    return random.choice(BG_LIST)
