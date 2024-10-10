from pathlib import Path

import cv2
import toml


if __name__ == '__main__':

    path = Path(__file__).parent.parent / 'stages/editor-2160x1080'
    out_path = path.with_name('editor-1080x540')

    # For each directory
    for d in path.glob("**/"):
        # If crop.png exists
        crop = d / 'crop.png'
        meta = d / 'meta.toml'

        if not crop.exists():
            continue

        # Read the metadata and crop image
        meta_data = toml.loads(meta.read_text('utf-8'))
        crop_data = cv2.imread(str(crop))

        # Scale the metadata
        for key in ['start', 'end', 'offset']:
            if key in meta_data:
                for i in range(len(meta_data[key])):
                    meta_data[key][i] //= 2

        # Scale the crop image to its size / 2
        crop_data = cv2.resize(crop_data, (crop_data.shape[1] // 2, crop_data.shape[0] // 2))

        # Save the metadata and crop image to the new directory
        out_dir = out_path / d.name
        out_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_dir / 'crop.png'), crop_data)
        (out_dir / 'meta.toml').write_text(toml.dumps(meta_data), 'utf-8')
        # Copy preview.jpg to the new directory
        preview = d / 'preview.jpg'
        if preview.exists():
            (out_dir / 'preview.jpg').write_bytes(preview.read_bytes())
