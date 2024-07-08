import json
from datetime import datetime

import dateutil
from hypy_utils.tqdm_utils import tmap, pmap
from pandas import DataFrame

from consts import *


def parse(json_f: Path):
    data = json.loads(json_f.read_text('utf-8'))
    data = data['data']['eventRankings']
    # Process timestamps relative to the first timestamp
    # Parse ISO date 2024-03-15T16:51:00.539Z
    first = datetime.fromisoformat(data[0]['timestamp'][:-1]).timestamp()
    for d in data:
        t = int(datetime.fromisoformat(d['timestamp'][:-1]).timestamp() - first)
        # Round to half hopur
        t = t - t % 1800
        d['timestamp'] = t
    # Remove duplicate timestamp and keep the highest score
    data = {d['timestamp']: max(d1['score'] for d1 in data if d1['timestamp'] == d['timestamp']) for d in data}
    data = [{'timestamp': k, 'score': v} for k, v in data.items()]
    data.sort(key=lambda x: x['timestamp'])

    df = DataFrame(data)
    # Keep only timestamp, score
    df = df[['timestamp', 'score']]
    # Rename score to the file name (event id)
    df = df.rename(columns={'score': json_f.stem})
    return df


if __name__ == '__main__':
    # targets = DATA_PATH.glob("*/")
    targets = [DATA_PATH / f'{TARGET_RANK}']
    for t in targets:
        # Read event json and convert to csv
        jsons = t.glob("*.json")
        dfs = pmap(parse, jsons)

        # Graph dfs using plotly
        # Each event is a line series
        import plotly.express as px

        fig = px.line()
        for df in dfs:
            fig.add_scatter(x=df['timestamp'], y=df[df.columns[1]], name=df.columns[1])
        fig.show()

        # Combine all dataframes
        df = dfs[0]
        for d in dfs[1:]:
            df = df.merge(d, on='timestamp', how='outer')

        df.to_csv(CSV_PATH / f'{t.stem}.csv', index=False)





