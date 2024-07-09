"""
This script is used to clean the text story data from Project Sekai and prepare it for LoRA fine-tuning.
"""
import json
import re
from pathlib import Path

from hypy_utils.tqdm_utils import tmap, pmap

BASE_DIR = Path(r"C:\ws\Sekai\S3\sekai-jp-assets")
DATA_DIRS = [
    # All folders in the unitstory directory
    BASE_DIR / "scenario",
    # Scenario / profile_rip
    *(BASE_DIR / "scenario" / "profile_rip").glob("*/"),
    # All folders in the event_story directory
    *(BASE_DIR / "event_story").glob("*/"),
    # C:\ws\Sekai\S3\sekai-jp-assets\character\member
    *(BASE_DIR / "character" / "member").glob("*/"),
]


chara2ds = {v['id']: v for v in json.loads(Path('data/character2ds.json').read_text('utf-8'))}
chara_game = {v['id']: v for v in json.loads(Path('data/gameCharacters.json').read_text('utf-8'))}
chara_mob = {v['id']: v for v in json.loads(Path('data/mobCharacters.json').read_text('utf-8'))}


def find_chara_by_2d(chara2d: int):
    if isinstance(chara2d, str):
        chara2d = int(chara2d)
    if chara2d not in chara2ds:
        return None

    chara = chara2ds[chara2d]
    if chara['characterType'] == 'game_character':
        return chara_game[chara['characterId']]['givenName']
    else:
        return chara_mob[chara['characterId']]['name']


def find_chara(talk) -> str | None:
    # if there is only one TalkCharacters, then it is the speaker
    if len(talk['TalkCharacters']) == 1:
        chara = talk['TalkCharacters'][0]['Character2dId']
        if chara != 0:
            return find_chara_by_2d(chara)
    # If there is only one voice, then it is the speaker
    if len(talk['Voices']) == 1:
        chara = talk['Voices'][0]['Character2dId']
        if chara != 0:
            return find_chara_by_2d(chara)
        try:
            chara = int(talk['Voices'][0]['VoiceId'].split('_')[-1])
            return find_chara_by_2d(chara)
        except ValueError:
            return None


def normalize_anim(name: str) -> str | None:
    if name is None:
        return None
    # If it's a face
    if name.startswith('face_'):
        # Remove face prefix
        name = name[5:]
        # Remove _\d+
        name = re.sub(r'_\d+$', '', name)
    # If it's a motion animation
    if name.startswith('w-'):
        # Remove w- prefix
        name = name[2:]
        # Normalize to category_name_number
        # If it's the new format w-(\w+)-(\w+)(\d+)
        new_format = re.match(r'([a-z]+)-([a-z]+)(\d+)', name)
        if new_format:
            return f"{new_format.group(1)}_{new_format.group(2)}_{new_format.group(3)}"
        # If it's the old format w-(\w+)(\d+)-(\w+)
        old_format = re.match(r'([a-z]+)(\d+)-([a-z]+)', name)
        if old_format:
            return f"{old_format.group(1)}_{old_format.group(3)}_{old_format.group(2)}"
        # Warning
        print(f'Unknown format: {name}')
    return name


def remove_none(dic: dict):
    return {k: v for k, v in dic.items() if v is not None}


def parse_asset(asset: Path):
    # print(f"Processing {asset.name}")
    d = json.loads(asset.read_text('utf-8'))
    # Get TalkData
    talk_data = d.get('TalkData')
    if talk_data is None:
        return []

    def map_fn(talk):
        motion = (talk.get('Motions') or [{}])[0]
        voice = (talk.get('Voices') or [{}])

        return remove_none({
            'text': talk['Body'],
            'title': talk['WindowDisplayName'],
            'speaker': find_chara(talk),
            'animation': normalize_anim(motion.get('MotionName')),
            'face': normalize_anim(motion.get('FacialName')),
            'voice': voice[0].get('VoiceId') if voice else None
        })

    return [map_fn(talk) for talk in talk_data]


if __name__ == '__main__':
    # Open .asset files as json
    # assets = DATA_DIR.glob("*.asset")
    assets = sum([list(d.glob("**/*.asset")) for d in DATA_DIRS], [])

    # Parse and combine
    parsed = pmap(parse_asset, assets)
    all_parsed = [talk for talks in parsed for talk in talks]

    # Save
    Path('data/all_chat.json').write_text(json.dumps(all_parsed, ensure_ascii=False, indent=2), 'utf-8')
    print("Done")

    # Convert to training format
    # [
    #   {"text": "document"},
    #   {"text": "document"}
    # ]

    # First try (document)
    # <<SYS>>リアルなテキストメッセージのやり取りを書いてください。繰り返しを避けてください。<</SYS>>
    # ### speaker1: text1
    # ### speaker2: text2

    # Second try (document)
    # <<SYS>>リアルなテキストメッセージのやり取りを書いてください。繰り返しを避けてください。<</SYS>>
    # <|im_start|>speaker1 <{"animation":"w-adult01-blushed","face":"sleepy_01"}>
    # text1
    # <|im_end|>
    # <|im_start|>speaker2...
    training_data: list[dict] = []
    for conversation in parsed:
        # Convert conversation to plain text
        lines = [
            '<|im_start|>system',
            'リアルなテキストメッセージのやり取りを書いてください。繰り返しを避けてください。<|im_end|>'
        ]
        for talk in conversation:
            append_json = json.dumps(remove_none({'animation': talk.get('animation'), 'face': talk.get('face')}), ensure_ascii=False)
            if append_json == "{}":
                append_json = ""
            else:
                append_json = " " + append_json
            lines.append(f"<|im_start|>{talk.get('speaker') or talk.get('title')}{append_json}")
            lines.append(talk['text'] + "<|im_end|>")
        training_data.append({"text": "\n".join(lines)})

    Path('data/training_data_3.json').write_text(json.dumps(training_data, ensure_ascii=False, indent=2), 'utf-8')
    print("Done")

    # Convert to conversational training format
    # [{
    #     "instruction": "hi", (last chat message)
    #     "input": "",
    #     "output": "Hello!" (response)
    # }, ...]
    # Filter for 瑞希
    # training_data = []
    # last_chat = None
    # for chat in all_parsed:
    #     if chat['speaker'] == '瑞希':
    #         if last_chat is not None and last_chat['speaker'] != '瑞希':
    #             training_data.append({
    #                 "instruction": last_chat['text'],
    #                 "input": "",
    #                 "output": chat['text']
    #             })
    #     last_chat = chat
    #
    # Path('data/mizuki.json').write_text(json.dumps(training_data, ensure_ascii=False, indent=2), 'utf-8')