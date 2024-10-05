import json
import pickle
from pathlib import Path

import imagehash
from PIL import Image
from tqdm import tqdm

BASE_DIR = Path(r"Y:\Mugs\Sekai\sekai-jp-assets\music\jacket")


def cover_hash():
    # Compute and store perceptual hash of the cover image
    img = BASE_DIR.glob("*/jacket_s_*.png")
    hashes = {p.stem.split('_')[-1]: imagehash.phash(Image.open(str(p))) for p in tqdm(img)}
    with open("cover_hashes.pkl", "wb") as f:
        pickle.dump(hashes, f)


if __name__ == '__main__':
    cover_hash()