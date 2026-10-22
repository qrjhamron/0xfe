"""Persistent UCI workers: bounded queues/cache, legal moves, history, recovery."""
from collections import OrderedDict, deque
from dataclasses import dataclass
from functools import lru_cache
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

import chess
import chess.engine
from app_paths import ROOT


def engine_runtime_status():
    """Small public status object used by the panel and diagnostics."""
    binary = ROOT / 'runtime' / ('patricia.exe' if os.name == 'nt' else 'patricia')
    ready = binary.is_file()
    return {'backend': 'patricia', 'gpu': False, 'detected': ready,
            'reason': 'Patricia 5.1 terpasang' if ready else 'Patricia belum terpasang',
            'label': 'Patricia 5.1' if ready else 'Patricia belum terpasang'}


@dataclass(frozen=True)
class EngineSpec:
    key: str
    label: str
    command: object
    min_elo: int
    max_elo: int
    available: bool = True
    kind: str = "elo"
    fallback_command: object = None

    def panel(self):
        return {'label': self.label, 'min': self.min_elo, 'max': self.max_elo,
                'available': self.available, 'kind': self.kind}


# Patricia's published Skill_Level table (1-20); 21 is full strength and
# is never selected here. Panel Elo buttons map to the nearest level.
PATRICIA_SKILL_ELO = (500, 800, 1000, 1200, 1300, 1400, 1500, 1600, 1700, 1800,
                      1900, 2000, 2100, 2200, 2300, 2400, 2500, 2650, 2800, 3000)


def patricia_skill_for_elo(elo):
    """Nearest Patricia Skill_Level (1-20) for a panel Elo button."""
    return min(range(len(PATRICIA_SKILL_ELO)),
               key=lambda index: abs(PATRICIA_SKILL_ELO[index] - elo)) + 1


def engine_specs(stockfish=None):
    """Only Patricia ships now; the argument is kept for old call sites."""
    patricia = ROOT / 'runtime' / ('patricia.exe' if os.name == 'nt' else 'patricia')
    return {'patricia': EngineSpec('patricia', 'Patricia · agresif', [str(patricia)],
                                   500, 3000, patricia.is_file())}



@dataclass(frozen=True)
class Request:
    owner: str
    token: str
    game: str
    fen: str
    elo: int
    root_fen: str = ''
    history: tuple = ()
    nodes: int = 1
    analysis: bool = False
    multipv: int = 1
    # Metadata for the UI/status file; search identity stays governed by the
    # effective node count and position, so these fields do not alter caching.
    phase: str = 'fixed'
    base_nodes: int = 0
    # Stable player identity for persona-consistent candidate sampling, applied
    # outside the worker after the engine result arrives.
    persona: str = ''
    # Human-error toggles. Both default off so engine checks measure the
    # calibrated single-PV path unless a test opts in explicitly.
    blunders: bool = False
    panic: bool = False
    think_ms: int = 0
    style: str = 'balanced'

    @property
    def cache_key(self):
        return (self.fen, self.elo, self.root_fen, self.history, self.nodes, self.analysis, self.multipv, self.think_ms)


def reconstruct_board(request):
    """Use real UCI move history when it exactly reconstructs the displayed position."""
    target = chess.Board(request.fen)
    if request.history:
        try:
            # Live boards may omit startingFen even when SAN history is present.
            # Only accept the standard-root replay if its final position matches.
            board = chess.Board(request.root_fen or chess.STARTING_FEN)
            for san in request.history:
                board.push_san(san)
            if board.fen() == target.fen():
                return board
        except ValueError:
            pass
    return target


class EngineWorker:
    def __init__(self, spec, *, think=.4, threads=1, hash_mb=64, cache_size=128, idle_timeout=60):
        self.spec = spec
        self.active_command = spec.command
        self.using_fallback = False
        self.think, self.threads, self.hash_mb = think, threads, hash_mb
        self.cache_size = cache_size
        self.idle_timeout = idle_timeout
        self.condition = threading.Condition()
        self.pending = OrderedDict()
        self.latest = {}
        self.results = deque(maxlen=128)
        self.cache = OrderedDict()
        self.engine = None
        self.configured_elo = None
        self.stopped = False
        self.metrics = {'searches': 0, 'cache_hits': 0, 'incremental_hits': 0, 'restarts': 0, 'discarded': 0, 'idle_unloads': 0}
        self.incremental = {}
        self.thread = threading.Thread(target=self._run, name=f'coach-{spec.key}', daemon=True)
        self.thread.start()

    def submit(self, request):
        with self.condition:
            if self.stopped:
                return
            self.latest[request.owner] = request.token
            self.pending.pop(request.owner, None)
            self.pending[request.owner] = request
            # A tab can only have one queued request; keep a bounded number of tabs.
            while len(self.pending) > 32:
                _, dropped = self.pending.popitem(last=False)
                self.results.append({'request': dropped, 'engine': self.spec.key, 'move': None,
                                     'cached': False, 'latency_ms': 0,
                                     'error': 'Engine sibuk. Mencoba lagi…'})
            self.condition.notify()

    def cancel(self, owner):
        with self.condition:
            self.pending.pop(owner, None)
            self.latest.pop(owner, None)

    def drain(self):
        with self.condition:
            result = [r for r in self.results if self.latest.get(r['request'].owner) == r['request'].token]
            self.metrics['discarded'] += len(self.results) - len(result)
            self.results.clear()
            return result

    def _start(self):
        environment = dict(os.environ)
        environment.update({'OMP_NUM_THREADS': str(self.threads),
                            'MKL_NUM_THREADS': str(self.threads)})
        self.engine = chess.engine.SimpleEngine.popen_uci(self.active_command, timeout=20, env=environment)
        if 'Skill_Level' not in self.engine.options:
            raise chess.engine.EngineError('Patricia does not support Skill_Level')
        self.engine.configure({'Threads': self.threads, 'Hash': self.hash_mb})
        self.engine.ping()
        self.engine.timeout = 3
        self.configured_elo = None

    def _drop_engine(self):
        engine, self.engine = self.engine, None
        self.configured_elo = None
        if engine:
            engine.close()

    def _compute(self, request):
        board = reconstruct_board(request)
        if board.is_game_over():
            return {'move': None, 'cached': False}
        key = request.cache_key
        if key in self.cache:
            cached = self.cache.pop(key)
            if chess.Move.from_uci(cached['move']) in board.legal_moves:
                self.cache[key] = cached
                self.metrics['cache_hits'] += 1
                return {**cached, 'cached': True}
        for attempt in range(2):
            try:
                if self.engine is None:
                    self._start()
                if self.stopped:
                    return {'move': None, 'cached': False}
                if self.configured_elo != request.elo:
                    self.engine.configure(
                        {'Skill_Level': patricia_skill_for_elo(request.elo)})
                    self.configured_elo = request.elo
                budget = request.think_ms / 1000 if request.think_ms else self.think
                limit = chess.engine.Limit(
                    time=min(.25, budget) if request.analysis else budget)
                self.metrics['searches'] += 1
                # Stable game identity retains engine state/hash between moves.
                identity = (request.owner, request.game)
                previous=self.incremental.get(identity)
                if previous and request.history[:len(previous[0])] == previous[0]:
                    self.metrics['incremental_hits'] += 1
                candidates = []
                if request.analysis and 'MultiPV' in self.engine.options:
                    lines = self.engine.analyse(board, limit, multipv=request.multipv, game=identity,
                                                info=chess.engine.INFO_SCORE | chess.engine.INFO_PV)
                    seen = set()
                    for line in lines:
                        pv = line.get('pv', [])
                        if not pv or pv[0] not in board.legal_moves or pv[0] in seen:
                            continue
                        seen.add(pv[0])
                        score = line.get('score')
                        candidates.append({'move':pv[0].uci(),
                                           'score_cp':score.pov(board.turn).score(mate_score=100000) if score else None})
                    move = chess.Move.from_uci(candidates[0]['move']) if candidates else None
                else:
                    result = self.engine.play(board, limit, game=identity)
                    move = result.move
                    if request.analysis and move:
                        candidates = [{'move':move.uci(),'score_cp':None}]
                if move is None or move not in board.legal_moves:
                    raise chess.engine.EngineError('Engine returned no legal move')
                computed = {'move':move.uci()}
                if request.analysis:
                    computed['candidates'] = candidates
                self.cache[key] = computed
                self.incremental[identity]=(request.history,request.fen)
                while len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
                return {**computed, 'cached': False}
            except (chess.engine.EngineError, TimeoutError, OSError) as exc:
                self._drop_engine()
                if self.stopped:
                    return {'move': None, 'cached': False}
                self.metrics['restarts'] += 1
                logging.warning('%s recovery (%s), attempt %s', self.spec.label, type(exc).__name__, attempt + 1)
                if attempt:
                    return {'move': None, 'cached': False, 'error': f'{self.spec.label} belum siap. Mencoba lagi…'}

    def _run(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.pending or self.stopped, timeout=self.idle_timeout)
                    if not self.pending and not self.stopped:
                        continue
                    if self.stopped:
                        return
                    _, request = self.pending.popitem(last=False)
                started = time.monotonic()
                try:
                    result = self._compute(request)
                except Exception as exc:
                    self._drop_engine()
                    logging.warning('%s request failed (%s)', self.spec.label, type(exc).__name__)
                    result = {'move': None, 'cached': False, 'error': f'{self.spec.label} gagal. Mencoba lagi…'}
                result.update({'request': request, 'engine': self.spec.key,
                               'latency_ms': round((time.monotonic() - started) * 1000)})
                with self.condition:
                    if self.latest.get(request.owner) == request.token and not self.stopped:
                        self.results.append(result)
                    else:
                        self.metrics['discarded'] += 1
        finally:
            self._drop_engine()

    def close(self):
        with self.condition:
            self.stopped = True
            self.pending.clear()
            self.condition.notify_all()
        if self.engine:
            self.engine.close()
        self.thread.join(timeout=4)


class EnginePool:
    def __init__(self, specs, **settings):
        self.specs, self.settings = specs, settings
        self.workers = {}

    def submit(self, engine, request):
        if engine not in self.specs or not self.specs[engine].available:
            raise ValueError('Requested engine is not installed')
        spec = self.specs[engine]
        if not isinstance(request.nodes, int) or not 1 <= request.nodes <= 256:
            raise ValueError('Node budget must be between 1 and 256')
        if not isinstance(request.multipv, int) or not 1 <= request.multipv <= 8:
            raise ValueError('Branch count must be between 1 and 8')
        if not spec.min_elo <= request.elo <= spec.max_elo:
            raise ValueError('Requested Elo is outside the engine range')
        for key, worker in self.workers.items():
            if key != engine:
                worker.cancel(request.owner)
        if engine not in self.workers:
            self.workers[engine] = EngineWorker(spec, **self.settings)
        self.workers[engine].submit(request)

    def cancel(self, owner):
        for worker in self.workers.values():
            worker.cancel(owner)

    def drain(self):
        return [result for worker in self.workers.values() for result in worker.drain()]

    def close(self):
        for worker in self.workers.values():
            worker.close()
