"""
This script is used to clean the text story data from Project Sekai and prepare it for LoRA fine-tuning.
"""
import json
import re
from collections import Counter
from pathlib import Path

from hypy_utils import write_json
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
chara_game_name = {v['givenName']: v for v in chara_game.values()}


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
    if not name or len(name) < 2:
        return None
    # If it's a face
    if 'face_' in name:
        # Remove face_ prefix by find (it could be 2D_face_...)
        name = name[name.find('face_') + 5:]
        # Remove _\d+
        # name = re.sub(r'_\d+$', '', name)
    # Special case... typo from the original dataset:
    elif name.startswith('face _'):
        name = name[6:].strip()
    # If it's a motion animation
    elif name[1] == '-':
        # Remove w- or m- or s- prefix
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
        print(f'Unknown animation: {name}')
    else:
        print(f'Unknown animation: {name}')
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

    # DS4 (document)
    # <|im_start|>system
    # リアルなテキストメッセージのやり取りを書いてください。繰り返しを避けてください。<|im_end|>
    # <|im_start|>speaker1
    # text1<|im_end|>
    # <|im_start|>speaker2...
    # <|im_start|>system
    # この会話は終了しました。<|im_end|>
    # training_data: list[dict] = []
    # for conversation in parsed:
    #     # Convert conversation to plain text
    #     lines = [
    #         '<|im_start|>system',
    #         'プロセカのメンバー間の会話のダイアログを書いてください。繰り返しを避けてください。<|im_end|>'
    #     ]
    #     for talk in conversation:
    #         lines.append(f"<|im_start|>{talk.get('speaker') or talk.get('title')}")
    #         lines.append(talk['text'] + "<|im_end|>")
    #     lines.append('<|im_start|>system\nこの会話は終了しました。<|im_end|>')
    #     training_data.append({"text": "\n".join(lines)})
    #
    # Path('data/training_data_4.json').write_text(json.dumps(training_data, ensure_ascii=False, indent=2), 'utf-8')
    # print("Done")

    # DS5: Convert to conversational training format
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

    # Face Classification dataset
    # [{"text": "text", "label": "face_01"}, ...]
    face_cls_data = []
    for chat in all_parsed:
        face = chat.get('face')
        if not face:
            continue
        face = re.sub('^(face_)*(nc|idol_|night_|wonder_|sg|os|band_|street_)', '', face).strip()
        face_cls_data.append({
            "text": chat['text'],
            "label": face
        })
    # Filter out faces that are used less than 50 times
    count = Counter([d['label'] for d in face_cls_data])
    face_cls_data = [d for d in face_cls_data if count[d['label']] > 50]
    select_faces = set(d['label'] for d in face_cls_data)
    print(f"Number of faces: {len(select_faces)}")
    write_json('data/cls/face_data.json', face_cls_data)

    # Write another face dataset with _\d+ removed
    for f in face_cls_data:
        f['label'] = re.sub(r'_\d+$', '', f['label'])
    print(f"Number of faces (w/o _\\d+): {len(set(d['label'] for d in face_cls_data))}")
    print(set(d['label'] for d in face_cls_data))
    write_json('data/cls/face_data_major_classes.json', face_cls_data)

    # Face classification for each speaker separately
    face_cls_data = {}
    for chat in all_parsed:
        face = chat.get('face')
        speaker = chat.get('speaker') or chat.get('title')
        if not face or not speaker or speaker not in chara_game_name:
            continue
        face = re.sub('^(face_)*(nc|idol_|night_|wonder_|sg|os|band_|street_)', '', face)
        if speaker not in face_cls_data:
            face_cls_data[speaker] = []
        # If it's not in the filtered >50 times list, skip
        if face not in select_faces:
            continue
        face_cls_data[speaker].append({
            "text": chat['text'],
            "label": face
        })
    for k, v in face_cls_data.items():
        write_json(f'data/cls/face/{k}.json', v)

        # Major classes only (remove _\d+)
        for f in v:
            f['label'] = re.sub(r'_\d+$', '', f['label'])
        write_json(f'data/cls/face/{k}_major_classes.json', v)

    # Animation Classification dataset
    # [{"text": "text", "label": "w-01_01"}, ...]
    anim_cls_data = []
    for chat in all_parsed:
        if 'animation' not in chat:
            continue
        anim_cls_data.append({
            "text": chat['text'],
            "label": chat['animation']
        })
    write_json('data/cls/anim_data.json', anim_cls_data)

