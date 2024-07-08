import requests
from hypy_utils import write_json
from hypy_utils.tqdm_utils import tmap

from consts import *

HTTP = requests.Session()


def dl_one(rank: int):
    f = DATA_PATH / f'event/{ANALYZING_EVENT}/{rank}.json'
    # Skip old events that are already downloaded
    res = HTTP.get(f"https://api.sekai.best/event/{ANALYZING_EVENT}/rankings/graph?region=jp&rank={rank}")
    res.raise_for_status()
    data = res.json()
    write_json(f, data)
    print(f"Downloaded {f}")


if __name__ == '__main__':
    ranks = (list(range(1, 101)) +
             [200, 300, 400, 500,
              1000, 1500, 2000, 2500, 3000, 4000, 5000,
              10000, 20000, 30000, 40000, 50000,
              100000, 200000, 300000])

    # 1. Download all ranks for the current event
    tmap(dl_one, ranks, desc="Downloading ranks", max_workers=10)

