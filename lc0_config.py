"""Pinned Lc0 and human-data Gyal networks; no claimed Elo calibration."""
LC0_VERSION = 'v0.32.1'
LC0_COMMIT = 'fd71a2d921b689c5f479d3227c3806c8e272d9c5'
WEIGHTS = {
    'badgyal8': ('Bad Gyal 8', 'badgyal-8', 3799966, '128×10'),
    'meangirl7': ('Mean Girl 7', 'meangirl-7', 3506691, '32×4'),
    'goodgyal5': ('Good Gyal 5', 'goodgyal-5', 3422292, '48×5'),
    'evilgyal6': ('Evil Gyal 6', 'evilgyal-6', 3468575, '48×5'),
}

def weight_url(filename, attachment):
    return f'https://github.com/dkappe/leela-chess-weights/files/{attachment}/{filename}.pb.gz'
