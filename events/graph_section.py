import json

from sekai.consts import *

import plotly.express as px
import pandas as pd
import plotly.graph_objects as go


def graph_filled():
    fig = go.Figure(data=[go.Mesh3d(
        x=df['rank'],
        y=df['timestamp'],
        z=df['score'],
        opacity=0.5,
    )])

    fig.update_layout(
        scene=dict(
            xaxis_title='Rank',
            yaxis_title='Timestamp',
            zaxis_title='Score'
        )
    )

    fig.show()


def graph_scatter(df: pd.DataFrame):
    fig = px.scatter_3d(df, x='rank', y='timestamp', z='score', color='score')
    fig.show()


if __name__ == '__main__':
    # Graph a 3D graph of the leaderboard
    # Height (z axis) is the score
    # x axis is the rank
    # y axis is the timestamp

    # 1. Load all data into a format of [{timestamp: t, rank: r, score: s}]
    data = []
    for f in (DATA_PATH / f'event/{ANALYZING_EVENT}').glob("*.json"):
        ds = json.loads(f.read_text('utf-8'))
        ds = ds['data']['eventRankings']
        ds = [d for d in ds if d]
        for d in ds:
            data.append({'timestamp': d['timestamp'], 'rank': d['rank'], 'score': d['score']})
    has_data = {d['rank'] for d in data}
    print(repr(sorted(list(has_data))))

    # 2. Sort by timestamp
    data.sort(key=lambda x: x['timestamp'])

    # 3. Graph the data
    df = pd.DataFrame(data)
    # Filter only the top 10000
    df1 = df.copy()
    df1 = df1[df1['rank'] <= 10000]
    graph_scatter(df1)

    # Filter 10000..100
    # df2 = df.copy()
    # df2 = df2[(df2['rank'] <= 10000) & (df2['rank'] > 100)]
    # graph_scatter(df2)

    # Log scale rank
    # df['rank'] = df['rank'].apply(lambda x: max(1, x))
    # df['rank'] = df['rank'].apply(lambda x: 1 / x)
    # graph_scatter(df)
