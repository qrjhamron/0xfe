({fen, move, skill, san, score, token}) => {
  const board = document.querySelector('wc-chess-board, chess-board');
  if (!board?.game || board.game.getFEN() !== fen) return 'no-board';
  const coach = window.__chessArrowCoach;
  const current = coach?.read();
  if (move && !current?.eligible) return 'not-eligible';
  if (move && current.token !== token) return 'stale-token';
  if (move && current.prefs.skill !== skill) return 'stale-skill';
  let svg = board.querySelector('#human-engine-arrow');
  if (!move) {
    svg?.remove();
    return true;
  }
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.id = 'human-engine-arrow';
    svg.setAttribute('viewBox', '0 0 800 800');
    svg.setAttribute('aria-label', 'Rekomendasi langkah');
    svg.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:30;overflow:visible';
    svg.innerHTML = '<defs><marker id="human-arrow-tip" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="3" markerHeight="3" orient="auto"><path d="M 0 0 L 12 6 L 0 12 Z"/></marker></defs><line stroke-linecap="round" opacity=".88" marker-end="url(#human-arrow-tip)"/>';
    board.appendChild(svg);
  }
  const flipped = !!board.game.getOptions?.().flipped;
  const xy = square => {
    const file = square.charCodeAt(0) - 97, rank = Number(square[1]) - 1;
    return flipped ? [(7 - file) * 100 + 50, rank * 100 + 50]
      : [file * 100 + 50, (7 - rank) * 100 + 50];
  };
  const [x1, y1] = xy(move.slice(0, 2)), [x2, y2] = xy(move.slice(2, 4));
  const length = Math.hypot(x2 - x1, y2 - y1);
  const line = svg.querySelector('line');
  line.setAttribute('stroke', current.prefs.color);
  line.setAttribute('stroke-width', current.prefs.width);
  svg.querySelector('marker path').setAttribute('fill', current.prefs.color);
  for (const [key, value] of Object.entries({x1, y1, x2: x2 - (x2 - x1) * 18 / length, y2: y2 - (y2 - y1) * 18 / length})) line.setAttribute(key, value);
  svg.dataset.fen = fen;
  svg.dataset.move = move;
  svg.dataset.skill = String(skill);
  svg.dataset.token = token;
  coach.report({fen, move, skill, san, score, token});
  return true;
}
