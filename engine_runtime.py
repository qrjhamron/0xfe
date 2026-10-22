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
from maia_config import MODEL_NAME, MODEL_REVISION
from lc0_config import WEIGHTS
from app_paths import ROOT


def _env_true(name):
    return os.environ.get(name, '').strip().lower() in {'1', 'true', 'yes', 'on'}


@lru_cache(maxsize=16)
def _supported_lc0_backends(binary):
    """Read the backend list from the bundled Lc0 binary once.

    Windows releases are split into CPU and GPU builds.  Asking the binary for
    its advertised UCI values keeps the selector safe when a user replaces the
    bundled executable with a different build.
    """
    try:
        result = subprocess.run([str(binary), '--help', '--show-hidden'],
                                capture_output=True, text=True, timeout=4,
                                check=False)
        text = (result.stdout or '') + '\n' + (result.stderr or '')
        matches = re.findall(r'VALUES:\s*([^\r\n]+)', text, re.IGNORECASE)
        for raw in matches:
            values = tuple(x.strip().lower().rstrip(']') for x in raw.split(',') if x.strip())
            if any(name in values for name in ('eigen', 'blas', 'openblas', 'cudnn', 'cuda', 'opencl')):
                return values
    except (OSError, subprocess.SubprocessError):
        pass
    return ()


@lru_cache(maxsize=1)
def _gpu_present():
    """Return whether Windows or an NVIDIA driver exposes a GPU probe."""
    if _env_true('LC0_FORCE_CPU'):
        return False
    if _env_true('LC0_USE_GPU'):
        return True
    if os.name == 'nt':
        powershell = shutil.which('powershell') or shutil.which('pwsh')
        if powershell:
            script = "(Get-CimInstance Win32_VideoController | Where-Object {$_.Name -notmatch 'Microsoft Basic|Remote Display'} | Measure-Object).Count"
            try:
                probe = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command', script],
                                       capture_output=True, text=True, timeout=4, check=False)
                if probe.returncode == 0 and int((probe.stdout or '0').strip() or 0) > 0:
                    return True
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
    nvidia_smi = shutil.which('nvidia-smi')
    if not nvidia_smi:
        return False
    try:
        probe = subprocess.run([nvidia_smi, '-L'], capture_output=True, text=True,
                               timeout=3, check=False)
        return probe.returncode == 0 and bool((probe.stdout or '').strip())
    except (OSError, subprocess.SubprocessError):
        return False


_LC0_RUNTIME = {'binary': None, 'backend': None, 'gpu': False,
                'detected': False, 'reason': 'Belum diperiksa'}


def _select_lc0_runtime():
    """Choose a GPU Lc0 build when available, with a verified CPU fallback."""
    cpu_binary = ROOT / 'runtime' / ('lc0.exe' if os.name == 'nt' else 'lc0')
    gpu_binary = ROOT / 'runtime' / 'lc0-gpu.exe'
    gpu_manifest = ROOT / 'runtime' / 'lc0-gpu-backend.txt'
    explicit = os.environ.get('LC0_BACKEND', '').strip().lower()
    gpu_backends = ('cudnn', 'cuda', 'opencl', 'onnx-dml', 'dml')
    detected = _gpu_present()
    _LC0_RUNTIME['detected'] = detected
    gpu_ready = gpu_binary.is_file() and (os.name != 'nt' or gpu_manifest.is_file())
    if gpu_ready and (detected or explicit in gpu_backends):
        supported = _supported_lc0_backends(str(gpu_binary))
        backend = explicit if explicit and explicit != 'auto' else next(
            (name for name in gpu_backends if name in supported), None)
        if backend and (not supported or backend in supported):
            _LC0_RUNTIME.update(binary=gpu_binary, backend=backend, gpu=True,
                                reason=f'GPU terdeteksi · backend {backend}')
            return gpu_binary, backend
        _LC0_RUNTIME['reason'] = 'GPU terdeteksi, tetapi backend DirectML tidak tersedia'
    elif detected and not gpu_ready:
        _LC0_RUNTIME['reason'] = 'GPU terdeteksi, tetapi paket GPU belum lengkap · memakai CPU'
    elif detected:
        _LC0_RUNTIME['reason'] = 'GPU terdeteksi, tetapi binary GPU tidak ditemukan'
    else:
        _LC0_RUNTIME['reason'] = 'GPU tidak terdeteksi · memakai CPU'
    supported = _supported_lc0_backends(str(cpu_binary))
    backend = explicit if explicit and explicit != 'auto' else None
    if backend not in supported:
        preferred = ('blas', 'openblas', 'eigen') if os.name == 'nt' else ('eigen', 'openblas', 'blas')
        backend = next((name for name in preferred if name in supported), backend or preferred[0])
    _LC0_RUNTIME.update(binary=cpu_binary, backend=backend, gpu=False)
    return cpu_binary, backend


def lc0_runtime_status():
    """Small public status object used by the panel and diagnostics."""
    if _LC0_RUNTIME['binary'] is None:
        _select_lc0_runtime()
    return {'backend': _LC0_RUNTIME['backend'] or 'cpu',
            'gpu': bool(_LC0_RUNTIME['gpu']),
            'detected': bool(_LC0_RUNTIME['detected']),
            'reason': _LC0_RUNTIME['reason'],
            'label': ('GPU otomatis' if _LC0_RUNTIME['gpu'] else 'CPU otomatis')}


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


def engine_specs(stockfish):
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    # A frozen Windows build ships Maia as a sidecar executable. Source builds
    # continue to use the project venv, which keeps local development light.
    maia_worker = ROOT / ('maia-worker.exe' if os.name == 'nt' else 'maia-worker')
    maia_runner = [str(maia_worker)] if getattr(sys, 'frozen', False) and maia_worker.exists() else [
        str(python if python.exists() else sys.executable), '-m', 'maia3.uci']
    maia = maia_runner + [
            '--model', MODEL_NAME, '--revision', MODEL_REVISION, '--device', 'cpu', '--no-use-amp',
            '--use-uci-history', '--local-files-only', '--cache-dir',
            str(ROOT / 'runtime' / 'maia3-cache'), '--temperature', '0', '--multipv', '1']
    maia_ready = (ROOT / 'runtime' / 'maia3-install.json').exists()
    if getattr(sys, 'frozen', False):
        maia_ready = maia_ready and maia_worker.exists()
    else:
        maia_ready = maia_ready and python.exists()
    patricia = ROOT / 'runtime' / ('patricia.exe' if os.name == 'nt' else 'patricia')
    specs = {
        'stockfish': EngineSpec('stockfish', 'Stockfish', stockfish, 1320, 3190),
        # Restrict the UI to the model's supported human rating range, not the broad UCI input range.
        'maia3': EngineSpec('maia3', 'Maia 3 · 5M', maia, 600, 2600,
                            maia_ready),
        'patricia': EngineSpec('patricia', 'Patricia · agresif', [str(patricia)], 500, 3000,
                               patricia.is_file())}
    binary, backend = _select_lc0_runtime()
    cpu_binary = ROOT / 'runtime' / ('lc0.exe' if os.name == 'nt' else 'lc0')
    cpu_supported = _supported_lc0_backends(str(cpu_binary))
    cpu_backend = next((name for name in (('blas', 'openblas', 'eigen') if os.name == 'nt'
                                          else ('eigen', 'openblas', 'blas'))
                        if name in cpu_supported), 'blas' if os.name == 'nt' else 'eigen')
    for key, (label, filename, _, size) in WEIGHTS.items():
        weight = ROOT / 'runtime' / 'lc0-weights' / (filename + '.pb.gz')
        command = [str(binary), '--weights=' + str(weight), '--backend=' + backend,
                   '--threads=1', '--minibatch-size=1', '--nncache=20000']
        fallback = None
        if _LC0_RUNTIME['gpu']:
            fallback = [str(cpu_binary), '--weights=' + str(weight), '--backend=' + cpu_backend,
                        '--threads=1', '--minibatch-size=1', '--nncache=20000']
        specs[key] = EngineSpec(key, f'Lc0 · {label} · {size}', command, 600, 3190,
                               binary.is_file() and weight.is_file() and (ROOT / 'runtime/lc0-install.json').is_file(),
                               'nodes', fallback)
    return specs



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

    @property
    def cache_key(self):
        return (self.fen, self.elo, self.root_fen, self.history, self.nodes, self.analysis, self.multipv)


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
        environment.update({'OMP_NUM_THREADS': str(self.threads), 'MKL_NUM_THREADS': str(self.threads),
                            'OPENBLAS_NUM_THREADS': str(self.threads), 'HF_HUB_OFFLINE': '1',
                            'HF_HOME': str(ROOT / 'runtime' / 'huggingface')})
        self.engine = chess.engine.SimpleEngine.popen_uci(self.active_command, timeout=20, env=environment)
        if self.spec.key == 'stockfish':
            elo = self.engine.options.get('UCI_Elo')
            if not elo or 'UCI_LimitStrength' not in self.engine.options:
                raise chess.engine.EngineError('Stockfish does not support Elo limiting')
            self.engine.configure({'UCI_LimitStrength': True, 'Threads': self.threads, 'Hash': self.hash_mb})
        elif self.spec.key == 'maia3':
            # python-chess manages MultiPV itself; its default is already set by the CLI.
            self.engine.configure({'Temperature': '0'})
        elif self.spec.key == 'patricia':
            if 'Skill_Level' not in self.engine.options:
                raise chess.engine.EngineError('Patricia does not support Skill_Level')
            self.engine.configure({'Threads': self.threads, 'Hash': self.hash_mb})
        elif self.spec.kind == 'nodes':
            self.engine.configure({'Threads': self.threads, 'MinibatchSize': 1,
                                   'NNCacheSize': 20000, 'SmartPruningFactor': '0', 'RamLimitMb': 128, 'MaxPrefetch': 0})
        self.engine.ping()  # Preload Maia inside its worker, without blocking the browser loop.
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
        key = ((request.fen, request.nodes, request.root_fen, request.history, request.analysis, request.multipv)
               if self.spec.kind == 'nodes' else request.cache_key)
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
                if self.spec.kind != 'nodes' and self.configured_elo != request.elo:
                    if self.spec.key == 'stockfish':
                        option, value = 'UCI_Elo', request.elo
                    elif self.spec.key == 'patricia':
                        option, value = 'Skill_Level', patricia_skill_for_elo(request.elo)
                    else:
                        option, value = 'Elo', request.elo
                    self.engine.configure({option: value})
                    self.configured_elo = request.elo
                limit = (chess.engine.Limit(nodes=request.nodes, time=.4 if request.analysis else 2) if self.spec.kind == 'nodes' else
                         chess.engine.Limit(time=min(.2,self.think) if request.analysis else self.think) if self.spec.key in ('stockfish', 'patricia') else chess.engine.Limit(nodes=1))
                self.metrics['searches'] += 1
                # Stable game identity retains engine state/hash between moves.
                identity = (request.owner, request.game, request.nodes) if self.spec.kind == 'nodes' else (request.owner, request.game)
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
                if self.spec.fallback_command and not self.using_fallback:
                    self.active_command = self.spec.fallback_command
                    self.using_fallback = True
                    logging.warning('%s GPU unavailable (%s); falling back to CPU',
                                    self.spec.label, type(exc).__name__)
                    continue
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
                        # Release dormant neural models without losing their small move cache.
                        if self.spec.kind == 'nodes' and self.engine is not None:
                            self._drop_engine()
                            self.metrics['idle_unloads'] += 1
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
