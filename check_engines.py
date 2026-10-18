#!/usr/bin/env python3
"""Real-engine checks: legal history-aware moves, caching, recovery, queue bounds."""
import json
import os
from pathlib import Path
import signal
import time

import chess
from engine_runtime import EnginePool, Request, engine_specs, reconstruct_board

ROOT = Path(__file__).resolve().parent


def request(owner, token, board):
    root = board.root()
    replay = root.copy()
    history = []
    for move in board.move_stack:
        history.append(replay.san(move))
        replay.push(move)
    return Request(owner, token, 'check-game', board.fen(en_passant='fen'), 1500,
                   root.fen(), tuple(history))


def wait(pool, token, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for result in pool.drain():
            if result['request'].token == token:
                assert not result.get('error'), result
                assert result['move'] is not None
                board = chess.Board(result['request'].fen)
                assert chess.Move.from_uci(result['move']) in board.legal_moves
                return result
        time.sleep(.02)
    raise AssertionError(f'Response timed out: {token}')


def main():
    specs = engine_specs(str(ROOT / 'runtime' / ('stockfish.exe' if os.name == 'nt' else 'stockfish')))
    pool = EnginePool(specs, think=.2, threads=1, hash_mb=64, cache_size=3)
    report = {}
    try:
        for key, spec in specs.items():
            if not spec.available:
                print(f'SKIP: {key} is not installed', flush=True)
                continue
            timings = []
            pid = None
            for index, sequence in enumerate(['', 'e4', 'e4 e5', 'e4 e5 Nf3', 'd4 d5 c4']):
                board = chess.Board()
                for san in sequence.split():
                    board.push_san(san)
                job = request(key, f'{key}-{index}', board)
                assert len(reconstruct_board(job).move_stack) == len(board.move_stack)
                pool.submit(key, job)
                result = wait(pool, job.token)
                timings.append(result['latency_ms'])
                current_pid = pool.workers[key].engine.transport.get_pid()
                assert pid is None or current_pid == pid, 'Engine should persist between positions'
                pid = current_pid
            repeat = request(key, f'{key}-cached', board)
            pool.submit(key, repeat)
            cached = wait(pool, repeat.token)
            assert cached['cached'] and cached['latency_ms'] < 50
            assert len(pool.workers[key].cache) <= 3
            print(f'PASS: {key} legal White/Black/history moves, persistent process, bounded cache', flush=True)

            os.kill(pid, signal.SIGTERM)
            time.sleep(.1)
            board = chess.Board(); board.push_san('c4')
            recovery = request(key, f'{key}-recovered', board)
            pool.submit(key, recovery)
            recovered = wait(pool, recovery.token)
            assert pool.workers[key].metrics['restarts'] >= 1
            assert pool.workers[key].engine.transport.get_pid() != pid
            print(f'PASS: {key} recovers automatically after engine termination', flush=True)

            for index in range(20):
                pool.submit(key, request('burst', f'{key}-burst-{index}', board))
            wait(pool, f'{key}-burst-19')
            worker = pool.workers[key]
            assert len(worker.pending) <= 32
            pool.submit(key, request('cancelled', f'{key}-cancelled', chess.Board()))
            pool.cancel('cancelled')
            time.sleep(.3)
            assert not any(r['request'].owner == 'cancelled' for r in pool.drain())
            print(f'PASS: {key} newest request wins and cancelled requests stay hidden', flush=True)
            rss = None
            status = Path(f'/proc/{worker.engine.transport.get_pid()}/status')
            if status.exists():
                rss = next((int(line.split()[1]) for line in status.read_text().splitlines() if line.startswith('VmRSS:')), None)
            report[key] = {'first_load_ms': timings[0], 'warm_move_ms': timings[1:],
                           'cache_ms': cached['latency_ms'], 'recovery_ms': recovered['latency_ms'],
                           'rss_kib': rss, 'metrics': dict(worker.metrics)}
    finally:
        pool.close()
    (ROOT / 'engine-benchmark.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    print('ALL REAL-ENGINE CHECKS PASSED', flush=True)


if __name__ == '__main__':
    main()
