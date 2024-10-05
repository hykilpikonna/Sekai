from matplotlib import pyplot as plt
from scrcpy import ACTION_DOWN
from torch.nn.functional import one_hot
import plotly.graph_objects as go

from main import *


def visualize_tpo_debug(tpo):
    # Load image
    frame = np.load("frame.npy")
    # Draw the touch position
    cv2.circle(frame, (tpo, touch_y), 10, (0, 255, 0), -1)
    cv2.imshow("frame", frame)
    cv2.waitKey(0)


def generate_frame():
    # Generate a dummy frame with random bright spots
    frame = np.zeros((*ref_size, 3), dtype=np.uint8)
    if state == AState.WAIT_INIT:
        # Simulate lighted areas to trigger state change
        for i in range(12):
            x = visual_lc + i * ((visual_rc - visual_lc) // 12) + 5
            cv2.circle(frame, (x, visual_y), 2, (255, 255, 255), -1)
    return frame


def test():
    global igt
    load_song()
    igt = time.time_ns()
    start_time = time.time()
    duration = 30  # Run the simulation for 5 seconds
    interval = 1 / 60  # 60 FPS
    while time.time() - start_time < duration:
        frame = generate_frame()
        on_frame(frame)
        time.sleep(interval)
    # After simulation, visualize touch events
    visualize_touch_events()


def visualize_touch_events():
    # Ensure touch_events is not empty
    if not touch_events:
        print("No touch events to plot.")
        return

    # Group touch events by touch id
    ts = [[t for t in touch_events if t['tid'] == tid] for tid in set(t['tid'] for t in touch_events)]

    # Create a Plotly figure
    fig = go.Figure()

    # Plot touch x vs time (flipping axes, x on y-axis, time on x-axis)
    for one_touch in ts:
        x = [t['x'] for t in one_touch]    # X-coordinate on x-axis
        y = [t['time'] / 1_000_000_000 for t in one_touch]  # Time on y-axis
        fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', showlegend=False))  # Disabled legend

    # Add labels and a title
    fig.update_layout(
        title='Touch Events Over Time',
        xaxis_title='Touch X Position',
        yaxis_title='Time',
        showlegend=False # Disable legend
    )

    # Display the figure
    fig.show()


if __name__ == '__main__':
    test()