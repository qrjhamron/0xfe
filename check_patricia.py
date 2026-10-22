"""Patricia mode checks: Elo-to-skill mapping, routing, and a real UCI game.

The mapping and routing checks always run. The engine-pool check runs only
when runtime/patricia is installed (python3 setup_patricia.py); otherwise it
reports SKIP instead of failing, like the Maia probe in check_determinism.
"""
import time
from pathlib import Path
from types import SimpleNamespace

import chess

from arrows import engine_for_position, selected_preset
from engine_runtime import EnginePool, Request, engine_specs, patricia_skill_for_elo
from presets import Preset

ROOT = Path(__file__).resolve().parent

# Panel buttons land exactly on Patricia's own table.
for elo, skill in [(1500, 7), (1600, 8), (1700, 9), (1800, 10), (1900, 11), (2000, 12)]:
    assert patricia_skill_for_elo(elo) == skill, (elo, skill)
assert patricia_skill_for_elo(500) == 1 and patricia_skill_for_elo(3000) == 20
skills = [patricia_skill_for_elo(elo) for elo in range(500, 3001, 100)]
assert skills == sorted(skills), 'skill must not decrease as Elo rises'
print('PASS: Elo buttons map exactly onto Patricia Skill_Level 7-12 (full range 1-20)')

specs = engine_specs(str(ROOT / 'runtime/stockfish'))
preset = Preset(1500, 'badgyal8', 4, True, 1500, (1400, 1600), 60)
snapshot = {'prefs': {'elo': 1500, 'engine': 'patricia'}}
if specs['patricia'].available:
    assert engine_for_position('patricia', preset, SimpleNamespace(phase='middlegame'),
                               chess.STARTING_FEN, specs) == 'patricia'
    chosen = selected_preset(snapshot, specs)
    assert chosen.engine == 'patricia' and chosen.elo == 1500
    print('PASS: patricia mode routes to Patricia at the chosen panel level')
else:
    assert engine_for_position('patricia', preset, SimpleNamespace(phase='middlegame'),
                               chess.STARTING_FEN, specs) == 'badgyal8'
    print('SKIP: Patricia not installed; routing falls back to the calibrated preset')


def play(pool, fen, elo):
    req = Request('patricia-check', f'patricia-{fen[:8]}-{elo}', 'patricia-check',
                  fen, elo, nodes=1)
    pool.submit('patricia', req)
    end = time.monotonic() + 30
    while time.monotonic() < end:
        for result in pool.drain():
            if result['request'].token == req.token:
                assert not result.get('error'), result
                return result['move']
        time.sleep(.01)
    raise AssertionError('Patricia response timed out')


if specs['patricia'].available:
    pool = EnginePool(specs, threads=1, hash_mb=64, cache_size=64)
    try:
        for elo in (1500, 2000):
            move = play(pool, chess.STARTING_FEN, elo)
            assert chess.Move.from_uci(move) in chess.Board().legal_moves, move
        fen = 'r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3'
        move = play(pool, fen, 1700)
        assert chess.Move.from_uci(move) in chess.Board(fen).legal_moves, move
    finally:
        pool.close()
    print('PASS: Patricia worker returns legal moves at levels 1500/1700/2000')
else:
    print('SKIP: Patricia binary missing; run setup_patricia.py for the UCI check')
print('ALL PATRICIA CHECKS PASSED')
