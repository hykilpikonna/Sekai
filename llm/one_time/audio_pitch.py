from pathlib import Path

import librosa
import numpy as np
import pandas as pd
from hypy_utils import ensure_dir
from hypy_utils.tqdm_utils import tmap, pmap

from llm.audio import OUT_BASE

OUT_F = Path('data/audio_pitch.csv')
CACHE_PATH = ensure_dir('data/cache')


def compute_one(f: Path):
    out_f = CACHE_PATH / f.with_suffix('.npy').name
    if out_f.is_file():
        return

    y, sr = librosa.load(f)

    # 75 - 300 Hz is the range of human voice
    f0, v_flag, v_probs = librosa.pyin(y, fmin=75, fmax=300)

    # Write the pitch to a npy
    np.save(out_f, f0)


if __name__ == '__main__':
    # Collect audio pitch data for each clip in まふゆ
    if OUT_F.is_file():
        pitches = pd.read_csv(OUT_F)
    else:
        pitches = pd.DataFrame(columns=['File Path', 'Pitch'])

    # 1. List files in まふゆ
    files = (OUT_BASE / 'まふゆ').rglob('*.wav')

    # 2. Compute pitch for each file
    pmap(compute_one, list(files))

