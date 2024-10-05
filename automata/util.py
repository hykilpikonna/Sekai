

def intersection(corner1: tuple[int, int], corner2: tuple[int, int], y_line: int) -> int:
    """
    Calculate the x-intercept of a line that intersects the given y-line

    :param corner1: The first corner of the line (x, y)
    :param corner2: The second corner of the line (x, y)
    :param y_line: The y-line to intersect
    :return: The x-intercept of the line
    """
    x1, y1 = corner1
    x2, y2 = corner2

    if y1 == y2:  # If the line is horizontal, there's no slant to intersect
        raise ValueError(f"The line is horizontal, there's no slant to intersect (input: {corner1}, {corner2}, {y_line})")

    # Calculate slope (m)
    slope = (y2 - y1) / (x2 - x1)

    # Calculate x-intercept for the given y = y_line
    x_intercept = x1 + (y_line - y1) / slope

    return int(x_intercept)
