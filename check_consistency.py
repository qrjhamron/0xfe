"""Ten-game consistency evaluation: one persona plays like one person.

The same persona must repeat its repertoire, candidate picks, tempo, cursor
habits, and premove plans across games. No browser or engine needed.
"""
import time
from collections import deque
from types import SimpleNamespace

import chess

from arrows import choose_candidate
from auto_moves import AutoMoves
from engine_runtime import Request
from human_style import (cursor_bow, generate_persona, jitter_factor,
                         tempo_multiplier, valid_persona)
from opening_book import REPERTOIRE, lookup
from premove import Premove

PERSONA = 'Kuda-7'
GAMES = [f'game-{n}' for n in range(10)]
HISTORIES = [(), ('e4',), ('e4', 'e5'), ('d4',), ('d4', 'd5'), ('c4',),
             ('Nf3',), ('e4', 'e5', 'Nf3')]
POSITIONS = [
    chess.STARTING_FEN,
    'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2',
    'r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3',
    'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w KQkq - 0 6',
]


def board_for(history):
    board = chess.Board()
    for san in history:
        board.push_san(san)
    return board


def main():
    assert valid_persona(PERSONA) and valid_persona(generate_persona())
    assert not valid_persona(None) and not valid_persona('game-1;drop')
    print('PASS: persona ids validate; untrusted strings rejected')

    # 1. One repertoire across all ten games, every move legal.
    lines = []
    for game in GAMES:
        line = tuple(lookup(board_for(h), h, True, seed=PERSONA) for h in HISTORIES)
        assert all(move is None or chess.Move.from_uci(move) in board_for(h).legal_moves
                   for move, h in zip(line, HISTORIES)), game
        lines.append(line)
    assert len(set(lines)) == 1, 'same persona must repeat its repertoire in every game'
    assert all(move in REPERTOIRE[h] for line in lines for move, h in zip(line, HISTORIES) if move)
    print('PASS: 10/10 games repeat the same persona repertoire, all moves legal')

    # 2. Same persona+position picks the same candidate under ten game tokens.
    result = {'move': 'e2e4', 'candidates': [
        {'move': 'e2e4', 'score_cp': 20}, {'move': 'd2d4', 'score_cp': -30},
        {'move': 'g1f3', 'score_cp': -200}]}
    picks = {choose_candidate(Request(f'owner-{n}', f'token-{game}', game,
                                      chess.STARTING_FEN, 1500, persona=PERSONA),
                              result)[0] for n, game in enumerate(GAMES)}
    assert len(picks) == 1, picks
    print(f'PASS: 10/10 game tokens pick the same candidate ({next(iter(picks))})')

    # 3. Same persona+position waits identically; fingerprints stay bounded.
    for fen in POSITIONS:
        board = chess.Board(fen)
        delays = set()
        for game in GAMES:
            s = {'token': f'{game}:{fen}', 'fen': fen,
                 'prefs': {'delay': 1200, 'persona': PERSONA,
                           'timeManagement': True, 'adaptiveDelay': True},
                 'turn': 'white', 'clocks': {'white': 180000, 'black': 180000}}
            delays.add(AutoMoves.adaptive_delay(s, board)[0])
        assert len(delays) == 1, (fen, delays)
    assert all(0.85 <= jitter_factor(PERSONA, fen) < 1.15 for fen in POSITIONS)
    assert 0.9 <= tempo_multiplier(PERSONA) <= 1.1
    print('PASS: 10/10 games wait identically per position; tempo fingerprint bounded')

    # 4. Same persona+move curves the cursor identically, within ±6px.
    for squares in (('e2', 'e4'), ('g1', 'f3'), ('e7', 'e5')):
        bows = {cursor_bow(PERSONA, *squares) for _ in GAMES}
        assert len(bows) == 1 and -6 <= next(iter(bows)) <= 6, squares
    assert cursor_bow(None, 'e2', 'e4') == 0
    print('PASS: cursor bow identical per persona+move and within ±6px')

    # 5. Same scripted position plans the same premove on repeated runs.
    class Pool:
        def __init__(self):
            self.jobs = deque()

        def cancel(self, owner):
            pass

        def submit(self, engine, req):
            self.jobs.append(req)

    s = {'prefs': {'elo': 1500, 'autoPremove': True, 'enabled': True, 'side': 'auto',
                   'premoveBreadth': 5, 'premovePolicy': 'balanced'},
         'phase': 'playing', 'atEnd': True, 'side': 'black', 'turn': 'white',
         'reason': 'opponent', 'gameId': 'one', 'revision': 0,
         'fen': chess.STARTING_FEN, 'history': [], 'rootFen': ''}
    preset = SimpleNamespace(engine='test', nodes=2)

    def run_plan():
        pool, planner = Pool(), Premove()
        planner.update(s, pool, preset)
        replies = {'e2e4': 'e7e5', 'd2d4': 'd7d5', 'g1f3': 'g8f6',
                   'c2c4': 'e7e5', 'g2g3': 'e7e5'}
        req = pool.jobs.popleft()
        planner.accept({'request': req, 'move': 'e2e4',
                        'candidates': [{'move': m, 'score_cp': 0} for m in replies]}, pool)
        for opponent, own in replies.items():
            planner.accept({'request': pool.jobs.popleft(), 'move': own}, pool)
        deadline = time.monotonic() + 4
        while planner.screen and time.monotonic() < deadline:
            planner.update(s, pool, preset)
        assert not planner.screen
        return planner.plan[0]['move'], [(b['opponent'], b['reply']) for b in planner.branches]

    first, second = run_plan(), run_plan()
    assert first == second and first[0] == 'e7e5', (first, second)
    print('PASS: premove plan identical across repeated runs of the same position')
    print('ALL CONSISTENCY CHECKS PASSED')


if __name__ == '__main__':
    main()
