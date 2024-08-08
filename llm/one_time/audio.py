import json
import shutil
from pathlib import Path
from subprocess import check_call

import torchaudio
from hypy_utils import ensure_dir
from hypy_utils.tqdm_utils import tmap

from clean import BASE_DIR

SR_TARGET = 22050
FFMPEG_PATH = 'ffmpeg'
OUT_BASE = Path(r'G:\custom_character_voice')
FULL_RES = 'full' in OUT_BASE.name


def build_audio_index() -> dict[str, Path]:
    """
    Build an index of all audio files in the Project Sekai assets.
    :return: A dictionary of audio file paths.
    """
    # Find all mp3 files in base directory
    audio_files = (BASE_DIR / 'sound').glob("**/*.mp3")
    # Build index
    return {f.stem: f for f in audio_files}


def normalize(inp: Path, output: Path) -> bool:
    """
    Normalize an audio file to a standard format.
    """
    # Ignore files > 10 seconds
    if librosa.get_duration(filename=str(inp)) > 10:
        return False

    if output.exists():
        return True

    # Full resolution mode for exporting, directly copy the file
    if FULL_RES:
        shutil.copy(inp, output)
        return True

    # Use ffmpeg to resample the audio to 22050 Hz (VITS)
    cmd = [FFMPEG_PATH, '-y', '-loglevel', 'error',
           '-i', str(inp),
           '-ar', str(SR_TARGET),
           '-ac', '1',
           str(output)]
    check_call(cmd)
    return True


speakers = [v['givenName'] for v in json.loads((Path(__file__).parent / 'data' / 'gameCharacters.json').read_text('utf-8'))]



def proc_one(chat: dict) -> str | None:
    # Get the voice id
    voice_id = chat.get('voice')
    if voice_id is None:
        return

    # Get the audio file
    audio_file = audio_index.get(voice_id)
    if audio_file is None:
        print(f"Missing audio file for {voice_id}")
        return

    # Normalize the audio
    output_file = ensure_dir(OUT_BASE / chat['speaker']) / f"{voice_id}.wav"
    if not normalize(audio_file, output_file):
        return

    # Write the annotation
    text: str = chat['text']
    text = text.replace('\n', '').replace('『', '').replace('』', '')
    return f"{output_file}|{chat['speaker']}|[JA]{text}[JA]"


def gather_voice_audio():
    """
    Gather the voice audio files from a given asset.
    """
    # Load all chat data
    print("Loading chat...")
    all_chat = json.loads(Path('data/all_chat.json').read_text('utf-8'))

    # FOR TESTING: Filter out only the first 10 by 瑞希
    # all_chat = [chat for chat in all_chat if chat.get('speaker') == '瑞希'][:10]
    # Filter speakers
    all_chat = [chat for chat in all_chat if chat.get('speaker') in speakers]
    # # Get first 200 for each speaker
    # chat_count = {speaker: 0 for speaker in speakers}
    #
    # def update_count(chat):
    #     chat_count[chat['speaker']] += 1
    #     return chat_count[chat['speaker']] <= 200
    # all_chat = [chat for chat in all_chat if update_count(chat)]

    # Build annotation format
    # ./custom_character_voice/speaker1/processed_0.wav|speaker1|[JA]こんにちは[JA]
    # ./custom_character_voice/speaker2/processed_2.wav|speaker2|[JA]こんにちは[JA]

    # For each text
    # 1. Normalize the audio and save to custom_character_voice
    # 2. Write the annotation to a file
    lst = tmap(proc_one, all_chat)
    annotations = '\n'.join(filter(None, lst))
    (OUT_BASE / 'short_character_anno.txt').write_text(annotations, 'utf-8')


if __name__ == '__main__':
    # Load the audio index
    print("Building audio index...")
    audio_index = build_audio_index()

    OUT_BASE.mkdir(exist_ok=True, parents=True)
    gather_voice_audio()
