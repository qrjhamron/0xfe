"""Tiny deterministic opening book used only for the first few plies."""
import chess

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
    ('d4',): 'd7d5',
    ('d4','d5'): 'c2c4',
    ('d4','d5','c4'): 'e7e6',
    ('d4','d5','c4','e6'): 'b1c3',
    ('c4',): 'e7e5',
    ('c4','e5'): 'b1c3',
    ('Nf3',): 'd7d5',
}

def lookup(board, history, enabled=True):
    if not enabled or len(history)>8:
        return None
    move=BOOK.get(tuple(history))
    if not move:
        return None
    candidate=chess.Move.from_uci(move)
    return move if candidate in board.legal_moves else None
