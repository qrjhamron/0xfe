"""Tiny deterministic opening book used only for the first twelve plies.

One persona keeps one repertoire: ``lookup`` accepts an optional ``seed``
(the stable persona id) so the same person repeats the same openings in
every game, while the legacy single-line book is kept for unseeded callers
and existing checks.
"""
import chess

from human_style import pick as persona_pick

MAX_BOOK_PLIES = 12

# SAN history is deliberately short and public; the book never replaces a
# tactical engine move after the opening leaves these common positions.
BOOK = {
    (): 'e2e4',
    ('e4',): 'e7e5',
    ('e4','e5'): 'g1f3',
    ('e4','e5','Nf3'): 'b8c6',
    ('e4','e5','Nf3','Nc6'): 'f1b5',
    ('e4','e5','Nf3','Nc6','Bb5'): 'a7a6',
    ('e4','e5','Nf3','Nc6','Bb5','a6'): 'b5a4',
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4'): 'g8f6',
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6'): 'e1g1',
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6','O-O'): 'f8e7',
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6','O-O','Be7'): 'f1e1',
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6','O-O','Be7','Re1'): 'b7b5',
    ('d4',): 'd7d5',
    ('d4','d5'): 'c2c4',
    ('d4','d5','c4'): 'e7e6',
    ('d4','d5','c4','e6'): 'b1c3',
    ('d4','d5','c4','e6','Nc3'): 'g8f6',
    ('d4','d5','c4','e6','Nc3','Nf6'): 'c1g5',
    ('d4','d5','c4','e6','Nc3','Nf6','Bg5'): 'f8e7',
    ('c4',): 'e7e5',
    ('c4','e5'): 'b1c3',
    ('Nf3',): 'd7d5',
}

# Human repertoire: common first moves and replies. The first entry of each
# list matches the legacy BOOK line, so seeded and unseeded play overlap on
# the most popular choice but seeded games vary across the rest.
REPERTOIRE = {
    (): ('e2e4', 'd2d4', 'c2c4', 'g1f3'),
    ('e4',): ('e7e5', 'c7c5', 'e7e6', 'c7c6'),
    ('d4',): ('d7d5', 'g8f6', 'e7e6'),
    ('c4',): ('e7e5', 'g8f6', 'c7c5'),
    ('Nf3',): ('d7d5', 'g8f6'),
    ('e4','e5'): ('g1f3', 'f1c4', 'd2d4'),
    ('e4','c5'): ('g1f3', 'd2d4'),
    ('e4','e6'): ('d2d4',),
    ('e4','c6'): ('d2d4',),
    ('d4','d5'): ('c2c4', 'g1f3', 'b1c3'),
    ('d4','Nf6'): ('c2c4', 'g1f3'),
    ('e4','e5','Nf3'): ('b8c6', 'g8f6'),
    ('e4','e5','Nf3','Nc6'): ('f1b5', 'f1c4', 'd2d4'),
    ('d4','d5','c4'): ('e7e6', 'c7c6'),
    ('d4','d5','c4','e6'): ('b1c3', 'g1f3'),
    ('c4','e5'): ('b1c3', 'g1f3'),
    # Main lines run about twelve plies deep, like memorized human theory.
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6'): ('e1g1',),
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6','O-O'): ('f8e7',),
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6','O-O','Be7'): ('f1e1',),
    ('e4','e5','Nf3','Nc6','Bb5','a6','Ba4','Nf6','O-O','Be7','Re1'): ('b7b5',),
    ('e4','e5','Nf3','Nc6','Bc4'): ('f8c5', 'g8f6'),
    ('e4','e5','Nf3','Nc6','Bc4','Bc5'): ('c2c3',),
    ('e4','e5','Nf3','Nc6','Bc4','Bc5','c3'): ('g8f6',),
    ('e4','e5','Nf3','Nc6','Bc4','Bc5','c3','Nf6'): ('d2d4',),
    ('e4','e5','Nf3','Nc6','Bc4','Bc5','c3','Nf6','d4'): ('e5d4',),
    ('e4','e5','Nf3','Nc6','Bc4','Bc5','c3','Nf6','d4','exd4'): ('c3d4',),
    ('e4','e5','Nf3','Nf6'): ('f3e5', 'd2d4'),
    ('e4','c5','Nf3'): ('d7d6',),
    ('e4','c5','Nf3','d6'): ('d2d4',),
    ('e4','c5','Nf3','d6','d4'): ('c5d4',),
    ('e4','c5','Nf3','d6','d4','cxd4'): ('f3d4',),
    ('e4','c5','Nf3','d6','d4','cxd4','Nxd4'): ('g8f6',),
    ('e4','e6','d4'): ('d7d5',),
    ('e4','e6','d4','d5'): ('b1c3',),
    ('e4','c6','d4'): ('d7d5',),
    ('e4','c6','d4','d5'): ('b1c3', 'e4e5'),
    ('d4','d5','c4','e6','Nc3'): ('g8f6',),
    ('d4','d5','c4','e6','Nc3','Nf6'): ('c1g5',),
    ('d4','d5','c4','e6','Nc3','Nf6','Bg5'): ('f8e7',),
    ('d4','d5','c4','e6','Nc3','Nf6','Bg5','Be7'): ('e2e3',),
    ('d4','d5','c4','e6','Nc3','Nf6','Bg5','Be7','e3'): ('e8g8',),
    ('d4','d5','c4','c6'): ('g1f3', 'b1c3'),
    ('d4','Nf6','c4'): ('g7g6',),
    ('d4','Nf6','c4','g6'): ('b1c3',),
    ('c4','e5','Nc3'): ('g8f6',),
    ('Nf3','d5'): ('c2c4', 'g2g3'),
    ('Nf3','Nf6'): ('c2c4',),
}


def _pick(options, seed, history):
    """Deterministically pick one candidate for this persona and position."""
    return persona_pick(options, seed, *history)


def lookup(board, history, enabled=True, seed=None):
    if not enabled or len(history) > MAX_BOOK_PLIES:
        return None
    key = tuple(history)
    if seed is not None:
        options = REPERTOIRE.get(key)
        if options:
            for _ in range(len(options)):
                candidate = chess.Move.from_uci(_pick(options, seed, key))
                if candidate in board.legal_moves:
                    return candidate.uci()
                # Extremely rare transposition mismatch: rotate once and retry.
                options = options[1:] + options[:1]
            return None
    move = BOOK.get(key)
    if not move:
        return None
    candidate = chess.Move.from_uci(move)
    return move if candidate in board.legal_moves else None
