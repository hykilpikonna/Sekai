import json
import random
from pathlib import Path

import pandas as pd

if __name__ == '__main__':
    """
    Generate prompts used for evaluation.
    
    Each entry contains a starting prompt and an expected responding speaker.
    """
    # Load game characters
    chars = json.loads(Path('data/gameCharacters.json').read_text('utf-8'))
    units = {c['unit'] for c in chars}
    print(f"There are {len(units)} units: {units}")

    # Only characters within the same unit knows each other. There are 6 units
    # Randomly create 100 prompts in each unit
    pairs = []
    for unit in units:
        for i in range(100):
            u_chars = [c for c in chars if c['unit'] == unit]

            # Randomly select a starting speaker
            speaker = random.choice(u_chars)['givenName']
            target = random.choice(u_chars)['givenName']
            while target == speaker:
                target = random.choice(u_chars)['givenName']

            # Build prompt
            pairs.append({
                'speaker': speaker,
                'target': target,
            })

    df = pd.DataFrame(pairs)
    df.to_csv('data/eval_prompts.csv', index=False)
