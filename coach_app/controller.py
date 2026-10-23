"""Coach controller: snapshot in, recommendation/auto-move intents out.

Qt-free on purpose: the window layer only forwards snapshots and renders
what this controller decides, so the logic stays checkable headlessly.
"""
import json
import time

import chess

from adaptive_strength import budget_for_position
from engine_runtime import EnginePool, Request, engine_specs
from human_style import choose_styled, ensure_persona
from opening_book import lookup as opening_lookup
from auto_moves import AutoMoves

from .geometry import resolve_side
from .snapshot import FenTracker

DEFAULT_SETTINGS = {
    'enabled': True, 'elo': 1500, 'style': 'balanced', 'side': 'auto',
    'color': '#20c4a0', 'width': 14, 'openingBook': True,
    'humanBlunders': True, 'autoMove': False, 'delay': 'natural',
    'think': 0.6, 'adaptiveStrength': True,
}


class CoachController:
    def __init__(self, on_recommendation=None, on_status=None, on_auto_move=None):
        self.settings = dict(DEFAULT_SETTINGS)
        self.on_recommendation = on_recommendation or (lambda payload: None)
        self.on_status = on_status or (lambda text: None)
        self.on_auto_move = on_auto_move or (lambda move: None)
        self.tracker = FenTracker()
        self.persona = ensure_persona()
        self.specs = engine_specs()
        self.pool = EnginePool(self.specs, threads=2, hash_mb=64, cache_size=128)
        self.pending_token = None
        self.book_token = None
        self.auto_job = None  # (token, execute_at, move_uci)
        self.last_payload = None

    def close(self):
        self.pool.close()

    def update(self, raw):
        """Advance one poll tick with a raw snapshot dict (or None)."""
        for result in self.pool.drain():
            self._accept(result)
        if not raw or not raw.get('fen'):
            self.on_status('Menunggu papan…')
            return
        history = self.tracker.update(raw['fen'])
        board = self.tracker.board
        fen = board.fen()
        if fen != raw['fen']:
            return
        side_pref = self.settings['side']
        side = resolve_side(raw.get('playing'), raw.get('flipped'), side_pref)
        turn = 'white' if board.turn == chess.WHITE else 'black'
        eligible = (self.settings['enabled'] and raw.get('result', '*') == '*'
                    and (side_pref == 'both' or side is None or turn == side))
        if not eligible:
            self.pending_token = None
            self.auto_job = None
            self.on_recommendation(None)
            self.on_status('Menunggu giliranmu' if raw.get('result', '*') == '*'
                           else 'Game selesai')
            return
        token = json.dumps([fen, side, self.settings['elo'], self.settings['style']])
        # Opening book first, exactly like the browser coach.
        if self.settings['openingBook'] and self.book_token != token:
            book_move = opening_lookup(board, history, True, seed=self.persona)
            if book_move:
                self.book_token = token
                self._deliver(board, book_move, token, [], None, 'opening-book')
                return
        if self.auto_job and self.auto_job[0] == token and time.monotonic() >= self.auto_job[1]:
            move = self.auto_job[2]
            self.auto_job = None
            self.on_auto_move(move)
            return
        if self.pending_token == token or (
                self.last_payload and self.last_payload['token'] == token):
            return
        budget = budget_for_position(board, 100, self.settings['adaptiveStrength'])
        think_ms = max(50, min(4000, round(self.settings['think'] * 1000 * budget.multiplier)))
        request = Request('coach-app', token, 'coach-app', fen, self.settings['elo'],
                          '', history, 16, True, 3, self.persona,
                          self.settings['humanBlunders'], False, budget.phase, 16,
                          think_ms, self.settings['style'])
        self.pending_token = token
        self.pool.submit('patricia', request)
        self.on_status('Menyiapkan…')

    def _accept(self, result):
        request = result['request']
        if request.token != self.pending_token or result.get('error') or not result.get('move'):
            return
        self.pending_token = None
        board = chess.Board(request.fen)
        chosen, _source = choose_styled(request, result)
        if not chosen:
            return
        candidates = [c['move'] for c in (result.get('candidates') or []) if c.get('move')]
        score = (result.get('candidates') or [{}])[0].get('score_cp')
        self._deliver(board, chosen, request.token, candidates, score, 'patricia')

    def _deliver(self, board, move_uci, token, candidates, score_cp, source):
        try:
            move = chess.Move.from_uci(move_uci)
            san = board.san(move)
        except (ValueError, AssertionError):
            return
        payload = {'fen': board.fen(), 'move': move_uci, 'san': san,
                   'candidates': candidates, 'score_cp': score_cp,
                   'token': token, 'source': source}
        self.last_payload = payload
        self.on_recommendation(payload)
        score_text = ''
        if isinstance(score_cp, (int, float)):
            pawns = score_cp / 100 if board.turn == chess.WHITE else -score_cp / 100
            score_text = f' · {pawns:+.1f}'
        self.on_status(f'{san}{score_text} · Skill {self._skill_label()}')
        if self.settings['autoMove']:
            clock_view = {'prefs': {'delay': 1200, 'timeManagement': True,
                                    'adaptiveDelay': True},
                          'turn': 'white' if board.turn == chess.WHITE else 'black',
                          'clocks': {}}
            delay, _reason = AutoMoves.adaptive_delay(clock_view, board)
            self.auto_job = (token, time.monotonic() + delay / 1000, move_uci)

    def _skill_label(self):
        from engine_runtime import patricia_skill_for_elo
        return patricia_skill_for_elo(self.settings['elo'])
