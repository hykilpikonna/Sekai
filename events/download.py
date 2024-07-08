import requests
from hypy_utils import write_json

from consts import *

HTTP = requests.Session()

if __name__ == '__main__':
    # 1. Download all event data
    for i in range(CUR_EVENT, MIN_EVENT, -1):
        f = DATA_PATH / f'{TARGET_RANK}/{i}.json'
        # Skip old events that are already downloaded
        if f.is_file() and not i == CUR_EVENT:
            continue
        res = HTTP.get(f"https://api.sekai.best/event/{i}/rankings/graph?region=jp&rank={TARGET_RANK}")
        res.raise_for_status()
        data = res.json()
        write_json(f, data)
        print(f"Downloaded {f}")
