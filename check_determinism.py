"""Real-engine determinism probe: fresh processes must repeat the same move.

Lc0 (nodes-based, the calibrated main path) is required. Maia 3 is probed
only when installed; it is documented as optional everywhere else. Stockfish
is excluded by design: its time-based search depth varies with machine load.
"""
import time
from pathlib import Path

import chess

from engine_runtime import EnginePool, Request, engine_specs
from presets import resolve_preset

POSITIONS = [
    chess.STARTING_FEN,
    'r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3',
]


def play(specs, engine, elo, nodes, fen):
    """Play one move with a fresh engine process, then shut it down."""
    pool = EnginePool(specs, threads=1, hash_mb=64, cache_size=64)
    try:
        req = Request('determinism', f'{engine}-{fen[:8]}', 'determinism',
                      fen, elo, nodes=nodes)
        pool.submit(engine, req)
        end = time.monotonic() + 30
        while time.monotonic() < end:
            for result in pool.drain():
                if result['request'].token == req.token:
                    assert not result.get('error'), result
                    assert not result['cached']
                    return result['move']
            time.sleep(.01)
        raise AssertionError(f'{engine} response timed out')
    finally:
        pool.close()


def main():
    root = Path(__file__).resolve().parent
    specs = engine_specs(str(root / 'runtime/stockfish'))
    preset = resolve_preset(1500, specs)
    for fen in POSITIONS:
        first, second = (play(specs, preset.engine, 1500, preset.nodes, fen)
                         for _ in range(2))
        assert first == second, (fen, first, second)
        assert chess.Move.from_uci(first) in chess.Board(fen).legal_moves
    print(f'PASS: {specs[preset.engine].label} repeats the same move from fresh processes')
    if specs['maia3'].available:
        for fen in POSITIONS:
            first, second = (play(specs, 'maia3', 1500, 1, fen) for _ in range(2))
            assert first == second, (fen, first, second)
            assert chess.Move.from_uci(first) in chess.Board(fen).legal_moves
        print('PASS: Maia 3 repeats the same move from fresh processes')
    else:
        print('SKIP: Maia 3 not installed; optional engine probe skipped')
    print('ALL DETERMINISM CHECKS PASSED')


if __name__ == '__main__':
    main()
