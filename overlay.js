({fen, move, elo, san, token, latency_ms, cached, phase, nodes_effective, adaptive_strength, candidates, score_cp}) => {
  const board = document.querySelector('wc-chess-board, chess-board');
  if (!board?.game || board.game.getFEN() !== fen) return false;
  const coach = window.__chessArrowCoach;
  const current = coach?.read();
  if (move && (!current?.eligible || current.token !== token || current.prefs.elo !== elo)) return false;
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
    svg.innerHTML = '<defs><marker id="human-arrow-tip" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="3" markerHeight="3" orient="auto"><path d="M 0 0 L 12 6 L 0 12 Z"/></marker></defs>';
    board.appendChild(svg);
  }
  const flipped = !!board.game.getOptions().flipped;
  const xy = square => {
    const file = square.charCodeAt(0) - 97, rank = Number(square[1]) - 1;
    return flipped ? [(7 - file) * 100 + 50, rank * 100 + 50]
      : [file * 100 + 50, (7 - rank) * 100 + 50];
  };
  // Main recommendation first, then up to two weaker candidate arrows,
  // thinner and fainter so the hierarchy reads at a glance.
  const moves = [move, ...(Array.isArray(candidates) ? candidates.map(c => c?.move) : [])]
    .filter((m, index, all) => typeof m === 'string' && m.length >= 4 && all.indexOf(m) === index)
    .slice(0, 3);
  const styles = [
    {width: current.prefs.width, opacity: .88},
    {width: Math.max(4, Math.round(current.prefs.width * .55)), opacity: .45},
    {width: Math.max(3, Math.round(current.prefs.width * .4)), opacity: .3}
  ];
  while (svg.querySelectorAll('line').length < moves.length) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('stroke-linecap', 'round');
    line.setAttribute('marker-end', 'url(#human-arrow-tip)');
    svg.appendChild(line);
  }
  const lines = [...svg.querySelectorAll('line')];
  lines.forEach((line, index) => {
    if (index >= moves.length) { line.setAttribute('opacity', '0'); return; }
    const candidate = moves[index];
    const [x1, y1] = xy(candidate.slice(0, 2)), [x2, y2] = xy(candidate.slice(2, 4));
    const length = Math.hypot(x2 - x1, y2 - y1) || 1;
    line.setAttribute('stroke', current.prefs.color);
    line.setAttribute('stroke-width', styles[index].width);
    line.setAttribute('opacity', styles[index].opacity);
    for (const [key, value] of Object.entries({x1, y1, x2: x2 - (x2 - x1) * 18 / length, y2: y2 - (y2 - y1) * 18 / length})) line.setAttribute(key, value);
  });
  svg.querySelector('marker path').setAttribute('fill', current.prefs.color);
  svg.dataset.fen = fen;
  svg.dataset.move = move;
  svg.dataset.elo = String(elo);
  svg.dataset.flipped = String(flipped);
  svg.dataset.token = token;
  svg.dataset.cached = String(!!cached);
  svg.dataset.latencyMs = String(latency_ms);
  coach.report({fen, move, elo, san, token, latency_ms, cached, phase, nodes_effective, adaptive_strength, candidates, score_cp});
  return true;
}
