"""Stable player identity for human-like, cross-game-consistent behavior.

One installation plays as one persona: the same person keeps the same
repertoire, tempo fingerprint, and cursor habits across games. Every
humanization seed therefore derives from (persona, position), never from a
per-game id, per-load token, or random uuid.
"""
import hashlib
import json
import random
import re

from app_paths import ROOT

PERSONA_PATTERN = re.compile(r'^[A-Za-z]+-\d{1,3}$')
_PERSONA_WORDS = ('Kuda', 'Gajah', 'Benteng', 'Menteri', 'Raja', 'Pion')
PERSONA_FILE = ROOT / 'runtime' / 'persona.json'


def valid_persona(value):
    return isinstance(value, str) and bool(PERSONA_PATTERN.match(value))


def generate_persona():
    return f'{random.choice(_PERSONA_WORDS)}-{random.randint(1, 99)}'


def ensure_persona():
    """Daemon-side fallback identity; the panel prefs remain the source of truth."""
    try:
        data = json.loads(PERSONA_FILE.read_text())
        if valid_persona(data.get('persona')):
            return data['persona']
    except (OSError, ValueError):
        pass
    persona = generate_persona()
    try:
        PERSONA_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERSONA_FILE.write_text(json.dumps({'persona': persona}))
    except OSError:
        pass
    return persona


def stable_int(*parts, digest_size=2):
    """Deterministic integer from parts; identical inputs always match."""
    blob = '\x00'.join('' if part is None else str(part) for part in parts)
    digest = hashlib.blake2s(blob.encode(), digest_size=digest_size).digest()
    return int.from_bytes(digest, 'big')


def pick(options, persona, *parts):
    """Deterministically choose one option for this persona and position."""
    return options[stable_int(persona, *parts) % len(options)]


def jitter_factor(persona, *parts):
    """Natural tempo variation in [0.85, 1.15) for one persona+position.

    Missing or invalid personas return exactly 1.0, which keeps legacy
    snapshots and panel-free checks on their old timing.
    """
    if not valid_persona(persona):
        return 1.0
    return 0.85 + 0.30 * (stable_int(persona, *parts) / 65536)


def tempo_multiplier(persona):
    """One base tempo per persona, between 0.9x and 1.1x."""
    if not valid_persona(persona):
        return 1.0
    return 0.9 + 0.2 * (stable_int(persona, 'tempo', digest_size=1) / 255)


def cursor_bow(persona, from_square, to_square):
    """Small deterministic cursor bow in whole pixels, -6..6, per persona+move."""
    if not valid_persona(persona):
        return 0
    return (stable_int(persona, from_square, to_square, digest_size=1) % 13) - 6


def blunder_rate(elo):
    """Share of tactical spots where this level slips to a worse in-window move."""
    if elo <= 1500:
        return 0.08
    if elo <= 1600:
        return 0.06
    if elo <= 1700:
        return 0.05
    if elo <= 1800:
        return 0.04
    if elo <= 1900:
        return 0.03
    return 0.02


def is_slip(persona, fen, elo):
    """Deterministic blind spot: one persona always decides the same spot alike."""
    return (stable_int(persona, fen, 'blunder') / 65536) < blunder_rate(elo)


def panic_nodes(base_nodes, remaining_ms):
    """Deterministic time-pressure budget; unknown clocks keep the base budget."""
    if type(base_nodes) is not int or not 1 <= base_nodes <= 256:
        raise ValueError('Base node budget must be between 1 and 256')
    if not isinstance(remaining_ms, (int, float)):
        return base_nodes
    if remaining_ms < 10000:
        return max(1, base_nodes // 4)
    if remaining_ms < 30000:
        return max(1, base_nodes // 2)
    return base_nodes
