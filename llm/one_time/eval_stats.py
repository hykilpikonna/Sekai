from pathlib import Path

import pandas as pd

if __name__ == '__main__':
    def is_correct(row):
        # Check if the row responding speaker is the expected speaker
        a, b = row.response.strip().split('\n')[0].strip(), row.target.strip()
        return a == b

    # For each csv in data/eval/resp
    for csv in Path('data/eval/resp').glob('*.csv'):
        df = pd.read_csv(csv)
        df['correct'] = df.apply(is_correct, axis=1)
        # Print stats
        print(f"{csv}: {df.correct.mean() * 100:.2f}% correct")

