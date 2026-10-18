"""Small, deterministic phase policy for the human-strength node budget.

The calibrated preset remains the middle-game baseline.  Adaptive mode only
changes the search budget by a bounded amount and never changes the selected
model or Elo limiter.
"""
from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class PhaseBudget:
    phase: str
    multiplier: float
    nodes: int


# Conservative factors keep the calibrated middle-game budget as the anchor.
_FACTORS = {
    'opening': 0.75,
    'middlegame': 1.0,
    'endgame': 1.15,
    'tactical': 1.25,
}


def classify_phase(board: chess.Board) -> str:
    """Classify a position using only board facts, with a tactical override."""
    if board.is_check():
        return 'tactical'

    # A check-free opening gets a little less search while the book and policy
    # model handle familiar positions.  Stop early if material has already
    # changed substantially, which prevents an early tactical game being
    # treated as a quiet opening.
    non_pawn = sum(1 for piece in board.piece_map().values()
                   if piece.piece_type not in (chess.KING, chess.PAWN))
    queens = any(piece.piece_type == chess.QUEEN for piece in board.piece_map().values())
    if board.fullmove_number <= 10 and non_pawn >= 6:
        return 'opening'

    # Queenless low-material positions benefit from a small budget bump.  The
    # threshold deliberately leaves rook-and-queen middlegames at baseline.
    if not queens and non_pawn <= 6:
        return 'endgame'
    return 'middlegame'


def budget_for_position(board: chess.Board, base_nodes: int, enabled: bool = True) -> PhaseBudget:
    """Return a bounded integer budget and the phase used to derive it."""
    if type(base_nodes) is not int or not 1 <= base_nodes <= 256:
        raise ValueError('Base node budget must be between 1 and 256')
    phase = classify_phase(board) if enabled else 'fixed'
    multiplier = _FACTORS.get(phase, 1.0)
    nodes = min(256, max(1, int(base_nodes * multiplier + 0.5)))
    return PhaseBudget(phase, multiplier, nodes)
