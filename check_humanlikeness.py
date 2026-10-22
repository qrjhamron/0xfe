"""Quantitative human-likeness report with a local regression baseline.

Measures per level, over a fixed 20-position suite: move completion and
legality, mean centipawn loss against a fixed-depth Stockfish oracle, move
agreement with Maia 3 when installed, and the persona tempo fingerprint.
Takes several minutes: each position runs real engine searches.

The first run writes runtime/humanlikeness-baseline.json (gitignored,
machine-local). Later runs must match it exactly: every input here is
deterministic. Delete the baseline when the engine set changes.
"""
import json
import time
from pathlib import Path

import chess
import chess.engine

from arrows import choose_candidate, multipv_for_elo
from auto_moves import AutoMoves
from engine_runtime import EnginePool, Request, engine_specs
from presets import resolve_preset

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / 'runtime' / 'humanlikeness-baseline.json'
PERSONA = 'Kuda-7'
LEVELS = (1500, 2000)
ORACLE_DEPTH = 12
LINES = [
    ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'a6', 'Ba4', 'Nf6', 'O-O', 'Be7'],
    ['e4', 'c5', 'Nf3', 'd6', 'd4', 'cxd4', 'Nxd4', 'Nf6', 'Nc3', 'a6'],
    ['d4', 'd5', 'c4', 'e6', 'Nc3', 'Nf6', 'Bg5', 'Be7', 'e3', 'O-O'],
    ['d4', 'Nf6', 'c4', 'g6', 'Nc3', 'Bg7', 'e4', 'd6', 'Nf3', 'O-O'],
    ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5', 'c3', 'Nf6', 'd4', 'exd4'],
    ['e4', 'e6', 'd4', 'd5', 'Nc3', 'Nf6', 'e5', 'Nfd7', 'f4', 'c5'],
]
ENDGAMES = [
    '8/5pk1/6p1/7p/2P5/2K3P1/5P2/8 w - - 0 18',
    '6k1/6R1/5ppp/8/8/8/5PPP/6K1 b - - 0 1',
]


def suite():
    positions = []
    for line in LINES:
        board = chess.Board()
        positions.append(board.fen())
        for index, san in enumerate(line):
            board.push_san(san)
            if index + 1 in (4, 7, 10):
                positions.append(board.fen())
    positions.extend(ENDGAMES)
    seen, unique = set(), []
    for fen in positions:
        if fen not in seen:
            seen.add(fen)
            unique.append(fen)
    assert len(unique) == 18 + 2
    for fen in unique:
        assert not chess.Board(fen).is_game_over()
    return unique


def wait(pool, token, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for result in pool.drain():
            if result['request'].token == token:
                assert not result.get('error'), result
                return result
        time.sleep(.01)
    raise AssertionError(f'Engine response timed out: {token}')


def oracle_score(stockfish, board):
    info = stockfish.analyse(board, chess.engine.Limit(depth=ORACLE_DEPTH))
    return info['score'].pov(board.turn).score(mate_score=100000)


def main():
    positions = suite()
    specs = engine_specs(str(ROOT / 'runtime' / 'stockfish'))
    stockfish_path = str(ROOT / 'runtime' / 'stockfish')
    assert Path(stockfish_path).is_file(), 'Stockfish oracle missing; run install.py'
    report = {'positions': len(positions), 'maia': specs['maia3'].available, 'levels': {}}
    pool = EnginePool(specs, threads=1, hash_mb=64, cache_size=64)
    stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    stockfish.configure({'Threads': 1, 'Hash': 64})
    try:
        maia_moves = {}
        if specs['maia3'].available:
            for index, fen in enumerate(positions):
                req = Request('eval-maia', f'maia-{index}', 'eval', fen, 1500, nodes=1)
                pool.submit('maia3', req)
                maia_moves[fen] = wait(pool, req.token)['move']
        for elo in LEVELS:
            preset = resolve_preset(elo, specs)
            moves, cpls, delays = [], [], []
            for index, fen in enumerate(positions):
                req = Request('eval', f'eval-{elo}-{index}', 'eval', fen, elo,
                              nodes=preset.nodes, analysis=True,
                              multipv=multipv_for_elo(elo),
                              persona=PERSONA, blunders=True)
                result = wait(pool, req.token)
                move, _ = choose_candidate(req, result)
                board = chess.Board(fen)
                assert chess.Move.from_uci(move) in board.legal_moves, (elo, fen, move)
                moves.append(move)
                best = oracle_score(stockfish, board)
                board.push_uci(move)
                cpls.append(max(0, min(2000, best + oracle_score(stockfish, board))))
                snapshot = {'prefs': {'delay': 1200, 'persona': PERSONA,
                                      'timeManagement': True, 'adaptiveDelay': True},
                            'turn': 'white' if chess.Board(fen).turn else 'black',
                            'clocks': {'white': 180000, 'black': 180000}}
                delays.append(AutoMoves.adaptive_delay(snapshot, chess.Board(fen))[0])
            agreement = (sum(1 for fen, move in zip(positions, moves)
                             if maia_moves.get(fen) == move) / len(positions)
                         if maia_moves else None)
            report['levels'][str(elo)] = {
                'moves': moves, 'mean_cpl': sum(cpls) / len(cpls),
                'maia_agreement': agreement,
                'tempo_mean': sum(delays) / len(delays),
                'tempo_min': min(delays), 'tempo_max': max(delays)}
            print(f'level {elo}: mean CPL {sum(cpls) / len(cpls):.1f} · '
                  f'Maia agreement {agreement if agreement is None else f"{agreement:.0%}"} · '
                  f'tempo {sum(delays) / len(delays):.2f}s', flush=True)
    finally:
        stockfish.close()
        pool.close()
    if not BASELINE.is_file():
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f'BASELINE CREATED: {BASELINE} (machine-local; delete it when engines change)')
        print('ALL HUMANLIKENESS CHECKS PASSED')
        return
    expected = json.loads(BASELINE.read_text())
    if expected != report:
        for key in ('positions', 'maia'):
            if expected.get(key) != report.get(key):
                raise AssertionError(f'baseline mismatch at {key}: {expected.get(key)} != {report.get(key)}')
        for elo, want in expected['levels'].items():
            got = report['levels'][elo]
            for metric in ('moves', 'mean_cpl', 'maia_agreement', 'tempo_mean', 'tempo_min', 'tempo_max'):
                if want[metric] != got[metric]:
                    raise AssertionError(f'baseline mismatch at {elo}.{metric}')
        raise AssertionError('baseline mismatch')
    print(f'PASS: report matches {BASELINE} exactly')
    print('ALL HUMANLIKENESS CHECKS PASSED')


if __name__ == '__main__':
    main()
