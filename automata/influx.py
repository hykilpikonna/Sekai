from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import orjson
import requests
from hypy_utils import write_json, write
from hypy_utils.tqdm_utils import tmap
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from tqdm import tqdm

from events.consts import ANALYZING_EVENT
from .config import config
from .util import ImageFinder, ocr_extract_number

HTTP = requests.Session()
ANALYZING_EVENT = 145


def send(point: Point | list[Point] | list[dict]) -> None:
    if point is None:
        return
    if not isinstance(point, list):
        point = [point]
    if isinstance(point[0], dict):
        point = [Point.from_dict(p) for p in point]

    # Initialize the InfluxDB client
    client = InfluxDBClient(
        url=config.influx.url,
        token=config.influx.token,
        org=config.influx.org
    )

    # Create a write API instance
    write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        # Write the point to the specified bucket
        # write_api.write(bucket=config.influx.bucket, record=point)
        for i in tqdm(range(0, len(point), 1000)):
            write_api.write(bucket=config.influx.bucket, record=point[i:i + 1000])

    except Exception as e:
        print(f"An error occurred while writing to InfluxDB: {e}")

    finally:
        # Ensure the client is closed to free resources
        client.close()


OCR_RES = Path(__file__).parent / 'stages/editor-1080x536/ocr'
all_fields = lambda x: [file.stem.split('_', 2)[-1] for file in OCR_RES.glob(f'result_{x}_*')]
ifs = lambda x: {field: ImageFinder(f'ocr/result_{x}_{field}') for field in all_fields(x) if field != 'identify'}
pairs = {
    # 1: (ImageFinder('ocr/result_1_identify'), ifs(1)),
    3: (ImageFinder('ocr/result_3_identify'), ifs(3))
}


def ident_img(file: Path) -> dict | None:
    file = Path(file)
    id_file = file.parent / 'identify' / file.with_suffix('.json').name
    if id_file.exists():
        return orjson.loads(id_file.read_text('utf-8'))

    ny_tz = ZoneInfo("America/New_York")
    time = datetime.strptime(file.stem, "%Y%m%d-%H%M%S").replace(tzinfo=ny_tz)

    # Convert New York time to UTC
    time_utc = time.astimezone(ZoneInfo("UTC"))

    # Load image
    img = cv2.imread(str(file))
    if img is None:
        return None

    # For each result pair
    for screen_id, (identify, ifs) in pairs.items():
        if not identify.check(img):
            continue

        # Get regions
        regions = {field: finder.get_region(img) for field, finder in ifs.items()}

        # Use OCR to identify the number in these image regions
        extracted_data = {}
        for field, region_img in regions.items():
            number = ocr_extract_number(region_img)
            extracted_data[field] = number
            print(f"Extracted {field}: {number}")

        # Create point and return
        d = {"measurement": f"result_screen{screen_id}", "time": time_utc, "fields": extracted_data}
        write(id_file, orjson.dumps(d).decode('utf-8'))
        return d


def filter_points(a: list[dict]):
    # Clean data: Some points have incorrect OCR values (maybe too small or too big)
    # For each point, check:
    # - If the total P is smaller than the previous total P, remove
    # - If the total P is larger than previous total P + previous P * 10, remove
    def check(p: dict, i: int):
        if i == 0:
            return True
        prev = a[i - 1]
        prev_total = prev['fields']['p_total']
        total = p['fields']['p_total']
        if not total or not prev_total or not prev['fields']['p']:
            return False
        if total < prev_total:
            return False
        if total > prev_total + prev['fields']['p'] * 10:
            print(f"Removed point with incorrect P value: {p}")
            return False
        return True
    a = [p for i, p in enumerate(a) if check(p, i)]
    a = [p for i, p in enumerate(a) if check(p, i)]
    a = [p for i, p in enumerate(a) if check(p, i)]
    a = [p for i, p in enumerate(a) if check(p, i)]
    a = [p for i, p in enumerate(a) if check(p, i)]

    return a


def images_to_influx(bp: Path, force_account: str = ''):
    fs = sorted(list(bp.glob('*.webp')))
    points = [p for p in tmap(ident_img, fs) if p]

    if force_account:
        for p in points:
            p['tags'] = {"account": force_account}
        send(filter_points(points))
        return

    # Clean and categorize the points
    # The folder contains points from different accounts, so we need to separate them by account
    # Each account would have a different bonus, we can use that to separate them
    bonuses = {p['fields']['bonus'] for p in points}
    accounts = [[p for p in points if p['fields']['bonus'] == bonus] for bonus in bonuses]

    # Remove accounts with less than 10 entries
    accounts = [a for a in accounts if len(a) >= 10]

    for i, a in enumerate(accounts):
        for p in a:
            p['tags'] = {"account": i}

    new_accounts = tmap(filter_points, accounts, desc="Filtering points", max_workers=10)

    # Send the points to InfluxDB
    for a in new_accounts:
        send(a)

    print("All data successfully sent to InfluxDB.")


def dl_one(rank: int):
    f = Path(__file__).parent / f'data/event/{ANALYZING_EVENT}/{rank}.json'
    # if f.is_file():
    #     return json.loads(f.read_text('utf-8'))
    # Skip old events that are already downloaded
    res = HTTP.get(f"https://api.sekai.best/event/{ANALYZING_EVENT}/rankings/graph?region=jp&rank={rank}")
    res.raise_for_status()
    data = res.json()
    write_json(f, data)
    print(f"Downloaded {f}")
    return data


def sekai_to_influx():
    ranks = (list(range(1, 101)) +
             [200, 300, 400, 500,
              1000, 1500, 2000, 2500, 3000, 4000, 5000,
              10000, 20000, 30000, 40000, 50000,
              100000, 200000, 300000])

    # 1. Download all ranks for the current event
    rankings = tmap(dl_one, ranks, desc="Downloading ranks", max_workers=10)
    rankings = [entry for r in rankings for entry in r['data']['eventRankings']]

    # 2. Convert the downloaded data to InfluxDB points
    def to_point(rank: dict) -> Point:
        # Useful fields: timestamp, rank, eventId, score
        # Example timestamp: 2024-06-20T06:06:00.287Z
        return Point("event_rank") \
            .time(rank['timestamp']) \
            .tag("rank", int(rank['rank'])) \
            .tag("eventId", int(rank['eventId'])) \
            .field("score", int(rank['score']))

    points = tmap(to_point, rankings, desc="Converting to InfluxDB points", max_workers=10)

    # 3. Send the points to InfluxDB
    send(points)

    print("All data successfully sent to InfluxDB.")


def delete_all(measurement: str) -> None:
    client = InfluxDBClient(
        url=config.influx.url,
        token=config.influx.token,
        org=config.influx.org
    )
    # Set up the delete API
    delete_api = client.delete_api()

    # Define start and stop times for the deletion (delete all data from 1970 to now)
    start_time = "1970-01-01T00:00:00Z"
    stop_time = datetime.utcnow().isoformat() + "Z"

    # Delete data in the 'sekai' bucket with measurement 'event_rank'
    delete_api.delete(
        start=start_time,
        stop=stop_time,
        predicate=f'_measurement="{measurement}"',
        bucket=config.influx.bucket,
        org=config.influx.org
    )


if __name__ == '__main__':
    delete_all('result_screen3')
    sekai_to_influx()
    images_to_influx(Path(r'/workspace/rhythm-game/Sekai/Code/log'))
    images_to_influx(Path(r'/workspace/rhythm-game/Sekai/Code/log-host'), 'syama')
