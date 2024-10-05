from pathlib import Path

import pandas as pd
import tabulate

if __name__ == '__main__':
    def is_correct(row):
        # Check if the row responding speaker is the expected speaker
        a, b = row.response.strip().split('\n')[0].strip(), row.target.strip()
        return a == b

    src = Path(__file__).parent
    d = src.parent / 'data'

    # For each csv in data/eval/resp
    data = []
    for csv in Path(d / 'eval/resp').glob('*.csv'):
        df = pd.read_csv(csv)
        df['correct'] = df.apply(is_correct, axis=1)
        # Print stats
        # print(f"{csv.stem}: {df.correct.mean() * 100:.2f}% correct")
        data.append([csv.stem, round(df.correct.mean() * 100, 1)])

    # Sort
    data.sort(key=lambda x: x[1], reverse=True)

    # Print table
    print(tabulate.tabulate(data, headers=['Session', 'Accuracy'], tablefmt='github'))
    print()
