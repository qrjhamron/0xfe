"""Deterministic checks for phase-aware node budgeting."""
import chess

from adaptive_strength import budget_for_position, classify_phase


def main():
    opening = budget_for_position(chess.Board(), 8)
    assert opening.phase == 'opening' and opening.nodes == 6

    middle = chess.Board('r1bq1rk1/ppp2ppp/2np1n2/3Np3/1b2P3/2N5/PPP2PPP/R1BQKB1R w KQ - 0 11')
    assert classify_phase(middle) == 'middlegame'
    assert budget_for_position(middle, 8).nodes == 8

    endgame = chess.Board('8/5pk1/6p1/7p/2P5/2K3P1/5P2/8 w - - 0 18')
    end = budget_for_position(endgame, 8)
    assert end.phase == 'endgame' and end.nodes == 9

    check = chess.Board('6k1/6R1/5ppp/8/8/8/5PPP/6K1 b - - 0 1')
    check.turn = chess.BLACK
    assert budget_for_position(check, 8).phase == 'tactical'

    fixed = budget_for_position(chess.Board(), 8, enabled=False)
    assert fixed.phase == 'fixed' and fixed.nodes == 8
    assert budget_for_position(chess.Board(), 256).nodes <= 256
    print('PASS: opening/middlegame/endgame/tactical budgets stay bounded and toggleable')


if __name__ == '__main__':
    main()
