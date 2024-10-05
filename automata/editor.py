import cv2
import numpy as np
from pathlib import Path

import scrcpy
import toml
from adbutils import adb
from scrcpy import LOCK_SCREEN_ORIENTATION_1

from .config import config

# Global variables to store the starting point, ending point, and drawing state
start_point: tuple[int, int] | None = None
end_point: tuple[int, int] | None = None
drawing: bool = False
paused: bool = False


def draw_rectangle(event: int, x: int, y: int, flags: int, param: None) -> None:
    """Mouse callback function to draw a rectangle."""
    global start_point, end_point, drawing

    if event == cv2.EVENT_LBUTTONDOWN:
        start_point = (x, y)
        drawing = True
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            end_point = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_point = (x, y)


def on_frame(frame: np.ndarray) -> None:
    """Processes each video frame, allowing user interaction for rectangle drawing."""
    global paused, start_point, end_point
    if frame is None:
        return

    # Display the frame
    cv2.imshow('Video Frame', frame)

    # Handle user input
    key = cv2.waitKey(1)
    if key == ord('e'):
        # Edit mode
        # Wait for the rectangle to be drawn
        cv2.setMouseCallback('Video Frame', draw_rectangle)
        orig_frame = frame
        while True:
            frame = orig_frame.copy()
            if start_point and end_point:
                cv2.rectangle(frame, start_point, end_point, (255, 0, 0), 1)  # Draw rectangle outside the area

            cv2.imshow('Video Frame', frame)
            cv2.waitKey(1)

            if not drawing and end_point:
                # Ask for file name when done
                filename = input("Enter the name for the saved files: ").strip()
                if not filename:
                    print("No input provided, skipping save")
                    break

                # Save the edited image and cropped pixels
                save_files(frame, start_point, end_point, filename)
                print(f"Files saved to stages/editor/{filename}")
                break

        # Cleanup
        start_point = end_point = None


def save_files(frame: np.ndarray, start: tuple[int, int], end: tuple[int, int], name: str) -> None:
    """Saves the edited image, cropped pixels, and metadata."""
    output_dir = Path(f'stages/editor/{name}')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the edited image with rectangle
    preview_path = output_dir / 'preview.jpg'
    cv2.imwrite(str(preview_path), frame)

    # Crop the pixels within the rectangle
    crop = frame[start[1]:end[1], start[0]:end[0]]
    crop_path = output_dir / 'crop.png'
    cv2.imwrite(str(crop_path), crop)

    # Create metadata file
    metadata = {'start': [start[0], start[1]], 'end': [end[0], end[1]]}
    meta_path = output_dir / 'meta.toml'
    with meta_path.open('w') as f:
        toml.dump(metadata, f)


# Example usage with video capture
def main() -> None:
    # Find device
    client = scrcpy.Client(
        device=adb.device_list()[0],
        lock_screen_orientation=LOCK_SCREEN_ORIENTATION_1,
        max_fps=config.device.fps,
        bitrate=config.device.bitrate,
        max_width=config.device.screen_size[0]
    )

    client.add_listener(scrcpy.EVENT_INIT, lambda: print("Client started"))
    client.add_listener(scrcpy.EVENT_FRAME, on_frame)

    # Start the client
    client.start()


if __name__ == "__main__":
    main()
