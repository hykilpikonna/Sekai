import time

import requests
from hypy_utils.logging_utils import setup_logger
from hypy_utils.tqdm_utils import tmap

log = setup_logger()


def test(i, *args, **kwargs):
    log.info(f"Sent > {i}")
    resp = requests.post(f'{host}/llm/create', json={
        "name":  "千葉",
        "intro": {
            "speaker": "千葉",
            "text": "瑞希、はじめまして！私はあなたの従妹の千葉です。しばらくの間、ここに滞在します。よろしくお願いします。",
        }
    }).json()
    n0 = resp['next'][0]
    log.info(f"Recv < {i} - {n0['speaker']}: {n0['text']}")


if __name__ == '__main__':
    host = "http://localhost:27518"

    # Test 10 requests
    n = 10
    start = time.time()

    tmap(test, range(n), max_workers=2)
    log.warning(f"Time taken: {(time.time() - start) / n:.2f}s per response")