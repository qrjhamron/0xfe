"""Pure board/arrow geometry shared by the overlay and its checks.

Coordinates use the same 800x800 logical board space as the old web
overlay, so arrow proportions stay familiar. No Qt imports live here.
"""


def square_center(square, flipped):
    """Center of a square like 'e4' in 800x800 board space."""
    file = ord(square[0]) - 97
    rank = int(square[1]) - 1
    if flipped:
        return (7 - file) * 100 + 50, rank * 100 + 50
    return file * 100 + 50, (7 - rank) * 100 + 50


def arrow_points(move_uci, flipped):
    """Shortened arrow endpoints for one UCI move (tip stops 18px early)."""
    x1, y1 = square_center(move_uci[0:2], flipped)
    x2, y2 = square_center(move_uci[2:4], flipped)
    import math
    length = math.hypot(x2 - x1, y2 - y1) or 1
    return x1, y1, x2 - (x2 - x1) * 18 / length, y2 - (y2 - y1) * 18 / length


def arrow_styles(count, width):
    """(line width, opacity) per arrow rank: main full, alts weaker."""
    styles = [
        (width, 0.88),
        (max(4, round(width * 0.55)), 0.45),
        (max(3, round(width * 0.4)), 0.30),
    ]
    return styles[:max(0, min(3, count))]


def resolve_side(playing_as, flipped, preference):
    """Local player's color from the page API, else board orientation."""
    if preference in ('white', 'black'):
        return preference
    if playing_as in (1, 'white', 'w'):
        return 'white'
    if playing_as in (2, 'black', 'b'):
        return 'black'
    if preference == 'both':
        return None
    return 'black' if flipped else 'white'
