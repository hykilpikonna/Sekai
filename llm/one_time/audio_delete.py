from pathlib import Path

import pandas as pd
from hypy_utils.tqdm_utils import tq

if __name__ == '__main__':
    # Load audio_lengths.csv
    audio_lengths = pd.read_csv('audio_lengths.csv')

    # Load short_character_anno.txt
    anno = Path('short_character_anno.txt').read_text('utf-8').splitlines()
    anno = {line.split('|')[0]: line for line in anno}

    # Back up short_character_anno.txt
    Path('short_character_anno.bak.txt').write_text('\n'.join(anno.values()), 'utf-8')

    # For each entry > 10s
    for idx, row in tq(audio_lengths.iterrows(), 'Removing long audio files'):
        if row['Length (seconds)'] > 10:
            # Remove it from short_character_anno.txt
            if row['File Path'] not in anno:
                print(f"Failed to find {row['File Path']}")
                continue
            del anno[row['File Path']]

    # Write the new short_character_anno.txt
    Path('short_character_anno.txt').write_text('\n'.join(anno.values()), 'utf-8')
