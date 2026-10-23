"""Read-only page snapshot for the embedded Chess.com board.

The script only reads board state and geometry; it never creates or
modifies page elements (recommendations are drawn by the Qt overlay).
"""
import chess

SNAPSHOT_JS = """() => {
  const b = document.querySelector('wc-chess-board, chess-board');
  if (!b || !b.game) return '';
  const g = b.game;
  const r = b.getBoundingClientRect();
  let playing = null;
  try { playing = g.getPlayingAs(); } catch (e) {}
  let result = '*';
  try { result = g.getResult() || '*'; } catch (e) {}
  return JSON.stringify({
    fen: g.getFEN(),
    flipped: !!(g.getOptions && g.getOptions().flipped),
    playing: playing,
    result: result,
    rect: {x: r.x, y: r.y, w: r.width, h: r.height}
  });
}"""


class FenTracker:
    """Rebuilds the move history by diffing consecutive FEN snapshots."""

    def __init__(self):
        self.board = chess.Board()
        self.history = []

    def update(self, fen):
        """Accept one FEN; returns the SAN history tuple for the book."""
        if fen == self.board.fen():
            return tuple(self.history)
        for move in self.board.legal_moves:
            trial = self.board.copy()
            san = trial.san(move)
            trial.push(move)
            if trial.fen() == fen:
                self.board = trial
                self.history.append(san)
                return tuple(self.history)
        try:
            self.board = chess.Board(fen)
        except ValueError:
            self.board = chess.Board()
        self.history = []
        return ()
