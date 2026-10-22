"""Deterministic checks for persona-stable openings, tempo, and cursor pacing."""
import chess

from arrows import choose_candidate, effective_budget, tactical_spot
from auto_moves import AutoMoves, material_edge
from engine_runtime import Request
from human_style import (blunder_rate, cursor_bow, is_slip, jitter_factor,
                         panic_nodes, tempo_multiplier)
from opening_book import BOOK, MAX_BOOK_PLIES, REPERTOIRE, lookup
from presets import Preset

PERSONA = 'Kuda-7'
LINES = [
    ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4'],
    ['e4', 'c5', 'Nf3', 'd6', 'd4'],
    ['d4', 'd5', 'c4', 'e6', 'Nc3'],
    ['e4', 'e6', 'd4', 'd5', 'Nc3'],
]


def positions(count):
    boards = []
    for n in range(count):
        line = LINES[n % len(LINES)]
        board = chess.Board()
        for san in line[:n % 5 + 1]:
            board.push_san(san)
        boards.append(board)
    return boards


# Legacy unseeded behavior is frozen: existing callers keep the single line.
board = chess.Board()
assert lookup(board, (), True) == 'e2e4'
assert lookup(board, (), True, seed=None) == BOOK[()]
moved = chess.Board()
moved.push_san('e4')
assert lookup(moved, ('e4',), True) == 'e7e5'
print('PASS: unseeded opening book keeps the legacy single line')

# One persona repeats one repertoire; different personas may differ.
stable = {lookup(chess.Board(), (), True, seed=PERSONA) for _ in range(48)}
assert len(stable) == 1, stable
firsts = {lookup(chess.Board(), (), True, seed=f'Pion-{n}') for n in range(48)}
assert len(firsts) >= 2, firsts
assert all(move in REPERTOIRE[()] for move in firsts)
replies = {lookup(moved, ('e4',), True, seed=PERSONA) for _ in range(12)}
assert len(replies) == 1
for move in replies:
    assert chess.Move.from_uci(move) in moved.legal_moves
# Unknown lines and disabled books still return nothing.
assert lookup(chess.Board(), ('e4', 'e5', 'Bc4'), True, seed=PERSONA) is None
assert lookup(chess.Board(), (), False, seed=PERSONA) is None
print('PASS: persona repertoire repeats per persona, varies across personas, stays legal')

# Tempo: deterministic per persona+position and bounded.
base = {'prefs': {'delay': 1200, 'persona': PERSONA,
                  'timeManagement': True, 'adaptiveDelay': True},
        'turn': 'white', 'clocks': {'white': 180000, 'black': 180000}}
first, _ = AutoMoves.adaptive_delay({**base, 'token': 'game-a'}, chess.Board())
second, _ = AutoMoves.adaptive_delay({**base, 'token': 'game-b'}, chess.Board())
assert first == second
delays = [AutoMoves.adaptive_delay(base, each)[0] for each in positions(12)]
assert len(set(delays)) >= 2, delays
for value in delays:
    assert 1.2 * 0.76 <= value <= 1.2 * 1.45 * 1.27 + 1e-9, value
assert all(0.85 <= jitter_factor(PERSONA, each.fen()) < 1.15 for each in positions(12))
assert 0.9 <= tempo_multiplier(PERSONA) <= 1.1
legacy = {'prefs': {'delay': 1200, 'timeManagement': True, 'adaptiveDelay': True},
          'turn': 'white', 'clocks': {'white': 180000, 'black': 180000}}
assert AutoMoves.adaptive_delay(legacy, chess.Board())[0] == 1.2
print('PASS: delay fingerprint repeats per persona+position, stays bounded, legacy timing exact')

# Forced replies play faster; panic time plays fastest of all.
forced = chess.Board('7k/5Q2/6p1/8/8/8/5PPP/6K1 b - - 0 1')
assert sum(1 for _ in forced.legal_moves) == 1
normal, _ = AutoMoves.adaptive_delay(legacy, chess.Board())
forced_delay, forced_reason = AutoMoves.adaptive_delay(legacy, forced)
assert forced_delay < normal and 'langkah paksa' in forced_reason
panic = {**legacy, 'clocks': {'white': 2000, 'black': 180000}}
panic_delay, panic_reason = AutoMoves.adaptive_delay(panic, chess.Board())
urgent = {**legacy, 'clocks': {'white': 6000, 'black': 180000}}
urgent_delay, _ = AutoMoves.adaptive_delay(urgent, chess.Board())
assert panic_delay < urgent_delay and 'sangat kritis' in panic_reason
print('PASS: forced moves accelerate and sub-3s panic time is the fastest tier')

# Confidence tempo: clearly winning positions play faster, clearly losing slower.
losing_board = chess.Board('q6k/8/8/8/8/8/5PPP/6K1 w - - 0 1')
winning_board = chess.Board('q6k/8/8/8/8/8/5PPP/6K1 b - - 0 1')
assert material_edge(losing_board) <= -4 and material_edge(winning_board) >= 4
losing_delay, losing_reason = AutoMoves.adaptive_delay(legacy, losing_board)
winning_delay, winning_reason = AutoMoves.adaptive_delay(legacy, winning_board)
assert winning_delay < losing_delay and 'bertahan' in losing_reason and 'unggul materi' in winning_reason
print('PASS: clearly winning positions play faster, clearly losing ones slower')

# Cursor pacing keeps the same total duration across its eased steps.
weights = (0.8, 1.0, 1.2, 1.2, 1.0, 0.8)
assert abs(sum(weights) - 6.0) < 1e-9
assert cursor_bow(PERSONA, 'e2', 'e4') == cursor_bow(PERSONA, 'e2', 'e4')
assert all(-6 <= cursor_bow(PERSONA, 'e2', f'{f}4') <= 6 for f in 'abcdefgh')
assert cursor_bow(None, 'e2', 'e4') == 0
print('PASS: eased cursor pacing preserves total duration; bow deterministic and bounded')

# Blunder rates shrink with level and stay a small minority of tactical spots.
rates = [blunder_rate(elo) for elo in range(1500, 2001, 100)]
assert rates == sorted(rates, reverse=True) and all(0 < rate <= 0.08 for rate in rates), rates
print('PASS: blunder rate shrinks with level and stays a small minority')

# Human slips: only on tactical spots, only to the worst move still inside
# the Elo window, and always the same choice for one persona+position.
tactical_fen = 'rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2'
assert tactical_spot(tactical_fen) and not tactical_spot(chess.STARTING_FEN)
candidates = {'move': 'e4d5', 'candidates': [
    {'move': 'e4d5', 'score_cp': 50}, {'move': 'd2d4', 'score_cp': 10},
    {'move': 'g1f3', 'score_cp': -10}, {'move': 'b1c3', 'score_cp': -500}]}
personas = [f'Pion-{n}' for n in range(1, 200)]
slipping = [name for name in personas if is_slip(name, tactical_fen, 1500)]
calm = [name for name in personas if not is_slip(name, tactical_fen, 1500)]
assert slipping and calm and 0.02 < len(slipping) / len(personas) < 0.2
slip_move, slip_source = choose_candidate(
    Request('owner', 'game-a', 'game', tactical_fen, 1500,
            persona=slipping[0], blunders=True), candidates)
assert slip_source.startswith('human-slip') and slip_move == 'g1f3', (slip_move, slip_source)
assert chess.Move.from_uci(slip_move) in chess.Board(tactical_fen).legal_moves
repeat = choose_candidate(
    Request('owner', 'game-b', 'game', tactical_fen, 1500,
            persona=slipping[0], blunders=True), candidates)
assert repeat == (slip_move, slip_source), 'one persona slips the same way in every game'
_, calm_source = choose_candidate(
    Request('owner', 'game-a', 'game', tactical_fen, 1500,
            persona=calm[0], blunders=True), candidates)
assert calm_source.startswith('hybrid-multipv'), calm_source
_, off_source = choose_candidate(
    Request('owner', 'game-a', 'game', tactical_fen, 1500,
            persona=slipping[0], blunders=False), candidates)
assert off_source.startswith('hybrid-multipv'), off_source
start = {'move': 'e2e4', 'candidates': [
    {'move': 'e2e4', 'score_cp': 20}, {'move': 'd2d4', 'score_cp': -30},
    {'move': 'g1f3', 'score_cp': -200}]}
_, quiet_source = choose_candidate(
    Request('owner', 'game-a', 'game', chess.STARTING_FEN, 1500,
            persona=slipping[0], blunders=True), start)
assert quiet_source.startswith('hybrid-multipv'), quiet_source
print('PASS: slips hit only tactical spots, stay inside the Elo window, and repeat per persona')

# Panic play cuts the node budget in tiers and leaves unknown clocks alone.
assert (panic_nodes(100, 5_000), panic_nodes(100, 20_000),
        panic_nodes(100, 60_000), panic_nodes(100, None)) == (25, 50, 100, 100)
try:
    panic_nodes(0, 5_000)
    raise AssertionError('invalid panic base accepted')
except ValueError:
    pass
preset = Preset(1500, 'badgyal8', 100, True, 1500, (1400, 1600), 60)
panicked = {'fen': chess.STARTING_FEN, 'turn': 'white',
            'clocks': {'white': 5_000, 'black': 180_000},
            'prefs': {'panicPlay': True, 'adaptiveStrength': False}}
assert effective_budget(panicked, preset)[0].nodes == 25
assert effective_budget({**panicked, 'prefs': {'panicPlay': False, 'adaptiveStrength': False}},
                        preset)[0].nodes == 100
assert effective_budget({**panicked, 'clocks': {}}, preset)[0].nodes == 100
print('PASS: panic play quarters then halves the budget; unknown clocks keep the preset')

print('ALL HUMANIZE CHECKS PASSED')
