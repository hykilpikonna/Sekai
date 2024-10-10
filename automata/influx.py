import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import requests
from hypy_utils import write_json
from hypy_utils.tqdm_utils import tmap
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from tqdm import tqdm

from events.consts import ANALYZING_EVENT
from .config import config
from .util import ImageFinder, ocr_extract_number

HTTP = requests.Session()
ANALYZING_EVENT = 144


def send(point: Point | list[Point]) -> None:
    if point is None:
        return

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
        write_api.write(bucket=config.influx.bucket, record=point)
        # print("Data successfully written to InfluxDB.")

    except Exception as e:
        print(f"An error occurred while writing to InfluxDB: {e}")

    finally:
        # Ensure the client is closed to free resources
        client.close()


OCR_RES = Path(__file__).parent / 'stages/editor/ocr'
all_fields = lambda x: [file.stem.split('_', 2)[-1] for file in OCR_RES.glob(f'result_{x}_*')]
ifs = lambda x: {field: ImageFinder(f'ocr/result_{x}_{field}') for field in all_fields(x)}
pairs = {
    # 1: (ImageFinder('ocr/result_1_identify'), ifs(1)),
    3: (ImageFinder('ocr/result_3_identify'), ifs(3))
}


def ident_img(file: Path) -> Point:
    file = Path(file)
    ny_tz = ZoneInfo("America/New_York")
    time = datetime.strptime(file.stem, "%Y%m%d-%H%M%S").replace(tzinfo=ny_tz)

    # Convert New York time to UTC
    time_utc = time.astimezone(ZoneInfo("UTC"))

    # Load image
    img = cv2.imread(str(file))

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

        # Remove image
        # file.unlink()

        # Create point and return
        p = Point(f"result_screen{screen_id}") \
            .time(time_utc) \
            .field("user", config.influx.user)
        for field, value in extracted_data.items():
            p.field(field, value)

        return p


def images_to_influx():
    bp = Path(r'X:\rhythm-game\Sekai\Code\log')
    fs = list(bp.glob('*.webp')) + list(bp.glob('*.png'))

    def helper(x):
        send(ident_img(x))

    tmap(helper, fs)


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
    # Split into batches of 1000 points
    for i in tqdm(range(0, len(points), 1000)):
        send(points[i:i + 1000])

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
    sekai_to_influx()
    images_to_influx()
