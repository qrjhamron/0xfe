"""Stable player identity for human-like, cross-game-consistent behavior.

One installation plays as one persona: the same person keeps the same
repertoire, tempo fingerprint, and cursor habits across games. Every
humanization seed therefore derives from (persona, position), never from a
per-game id, per-load token, or random uuid.
"""
import hashlib
import json
import math
import random
import re

import chess

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


def tactical_spot(fen):
    """True when a human is most likely to slip: checks and captures around."""
    try:
        board = chess.Board(fen)
    except ValueError:
        return False
    if board.is_check():
        return True
    return any(board.is_capture(move) for move in board.legal_moves)


STYLES = ('solid', 'balanced', 'aggressive', 'wild', 'original')
_PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                 chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def _attack_value(board, uci):
    """How violent a candidate is: mate > check > capture > promotion."""
    try:
        move = chess.Move.from_uci(uci)
    except (ValueError, IndexError):
        return -1
    if move not in board.legal_moves:
        return -1
    value = 0
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        value += 3 + (_PIECE_VALUES.get(victim.piece_type, 1) if victim else 1)
    if move.promotion:
        value += 2
    board.push(move)
    if board.is_checkmate():
        value += 100
    elif board.is_check():
        value += 4
    board.pop()
    return value


def _elo_window(elo):
    return 130 if elo <= 1600 else 105 if elo <= 1800 else 80 if elo <= 2000 else 60 if elo <= 2200 else 42


def choose_styled(request, result):
    """Apply the Patricia style to one engine result.

    solid/original always take Patricia's top move (original additionally
    means zero candidate tuning of any kind). balanced keeps the existing
    human-like sampling. aggressive prefers the most violent candidate in
    the Elo window; wild flattens the sampling and sometimes drops to a
    weaker candidate on purpose.
    """
    top_move = result.get('move')
    candidates = [c for c in (result.get('candidates') or [])
                  if c.get('move') and isinstance(c.get('score_cp'), (int, float))]
    style = request.style if request.style in STYLES else 'balanced'
    if style in ('solid', 'original') or not candidates:
        return top_move, f'patricia-{style}'
    if style == 'aggressive':
        board = chess.Board(request.fen)
        window = _elo_window(request.elo)
        best_score = max(c['score_cp'] for c in candidates)
        pool = [c for c in candidates if c['score_cp'] >= best_score - window]
        ranked = sorted(pool, key=lambda c: (-_attack_value(board, c['move']),
                                             -c['score_cp'], c['move']))
        if ranked and _attack_value(board, ranked[0]['move']) > 0:
            return ranked[0]['move'], 'patricia-aggressive'
        return top_move, 'patricia-aggressive'
    if style == 'wild':
        window = _elo_window(request.elo) * 2
        best_score = max(c['score_cp'] for c in candidates)
        pool = [c for c in candidates if c['score_cp'] >= best_score - window] or candidates
        rng = random.Random(stable_int(request.persona, request.fen, 'wild'))
        if len(pool) > 1 and rng.random() < .35:
            return rng.choice(pool[1:])['move'], 'patricia-wild'
        temperature = 90 + max(0, 2000 - request.elo) * .03
        weights = [math.exp((c['score_cp'] - best_score) / temperature) for c in pool]
        return rng.choices(pool, weights=weights, k=1)[0]['move'], 'patricia-wild'
    if request.blunders:
        return choose_candidate(request, result)
    return top_move, 'patricia'


def choose_candidate(request, result):
    candidates=result.get('candidates') or []
    if len(candidates)<2:
        return result.get('move'), 'engine'
    scored=[c for c in candidates if c.get('move') and isinstance(c.get('score_cp'),(int,float))]
    if not scored:
        return result.get('move'), 'engine'
    top=max(c['score_cp'] for c in scored)
    # Elo-limited window: lower levels may choose a plausible second/third move,
    # while high levels stay close to the principal variation.
    window=130 if request.elo<=1600 else 105 if request.elo<=1800 else 80 if request.elo<=2000 else 60 if request.elo<=2200 else 42
    pool=[c for c in scored if c['score_cp']>=top-window]
    if request.blunders and len(pool)>=2 and tactical_spot(request.fen):
        # A level-sized blind spot: the same persona always slips the same
        # way here, but only inside the plausible Elo window.
        if is_slip(request.persona,request.fen,request.elo):
            return pool[-1]['move'], f"human-slip-{len(candidates)}"
    temp=95 if request.elo<=1600 else 72 if request.elo<=1800 else 55 if request.elo<=2000 else 40 if request.elo<=2200 else 28
    weights=[math.exp((c['score_cp']-top)/temp) for c in pool]
    # Persona-stable sampling: the same person picks the same candidate from
    # the same position in every game, instead of reseeding per game token.
    target=(stable_int(request.persona,request.fen)/65536)*sum(weights)
    for candidate,weight in zip(pool,weights):
        target-=weight
        if target<=0:
            return candidate['move'], f"hybrid-multipv-{len(candidates)}"
    return pool[0]['move'], f"hybrid-multipv-{len(candidates)}"


