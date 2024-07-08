import json
from pathlib import Path

from consts import *

if __name__ == '__main__':
    # Read json
    data = json.loads(DATA_PATH / f'{TARGET_RANK}/130.json')
    data = data['data']['eventRankings']

    # Compute delta score in each hour