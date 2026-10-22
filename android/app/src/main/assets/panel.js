({skillLevels, defaultSkill}) => {
  const VERSION = 1;
  const GLOBAL = '__chessArrowCoach';
  if (window[GLOBAL]?.version === VERSION) return window[GLOBAL].read();
  window[GLOBAL]?.destroy?.();
  const boardSelector = 'wc-chess-board, chess-board';
  if (!document.querySelector(boardSelector)?.game) return null;
  const KEY = 'move-coach-android-v1';
  const levels = (Array.isArray(skillLevels) ? skillLevels : [])
    .filter(item => Number.isInteger(item?.skill) && Number.isInteger(item?.elo))
    .sort((a, b) => a.skill - b.skill);
  if (!levels.length) return null;
  const eloBySkill = new Map(levels.map(item => [item.skill, item.elo]));
  const fallbackSkill = eloBySkill.has(defaultSkill) ? defaultSkill : levels[0].skill;
  const initial = {enabled: true, skill: fallbackSkill, color: '#20c4a0', width: 14, side: 'auto', collapsed: false};
  const clean = value => ({
    enabled: typeof value?.enabled === 'boolean' ? value.enabled : initial.enabled,
    skill: eloBySkill.has(Number(value?.skill)) ? Number(value.skill) : initial.skill,
    color: /^#[a-f0-9]{6}$/i.test(value?.color || '') ? value.color : initial.color,
    width: Math.min(26, Math.max(6, Number(value?.width) || initial.width)),
    side: ['auto', 'white', 'black', 'both'].includes(value?.side) ? value.side : initial.side,
    collapsed: value?.collapsed === true
  });
  let prefs;
  try { prefs = clean(JSON.parse(localStorage.getItem(KEY))); } catch { prefs = clean(null); }
  let revision = 0;
  let alive = true;
  let lastMove = null;
  const instanceId = (() => { try { return crypto.randomUUID(); } catch { return String(Date.now()); } })();
  let lastGame = null, gameEpoch = 0, lastPlies = 0, lastResult = '*';
  const style = document.createElement('style');
  style.id = 'human-engine-panel-style';
  style.textContent = `
    #human-engine-panel {box-sizing:border-box;width:100%;margin:0 0 14px;padding:16px;
      background:linear-gradient(145deg,#23312b,#1b2420);color:#f2f5f3;border:1px solid #3b4b42;
      border-radius:14px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 6px 20px #0002;text-align:left}
    #human-engine-panel * {box-sizing:border-box}
    #human-engine-panel .coach-head {display:flex;align-items:center;justify-content:space-between;gap:12px}
    #human-engine-panel[data-collapsed=true] {padding-bottom:11px}
    #human-engine-panel .coach-collapse {width:30px;height:28px;padding:0;border:1px solid #465b4d;border-radius:7px;background:#17241c;color:#c4d1c8;font:700 16px/1 system-ui;cursor:pointer}
    #human-engine-panel .coach-eyebrow {color:#75c4a5;font-size:10px;letter-spacing:1.4px;font-weight:750}
    #human-engine-panel h2 {margin:3px 0 0;color:#f2f5f3;font-size:18px;line-height:1.2;font-weight:750}
    #human-engine-panel .coach-switch {display:flex;align-items:center;gap:6px;color:#cad8cf;font-size:12px;cursor:pointer}
    #human-engine-panel input[type=checkbox] {appearance:auto;width:17px;height:17px;accent-color:#20c4a0;margin:0}
    #human-engine-panel .coach-status {display:flex;align-items:center;gap:7px;margin:14px 0 10px;color:#b7c9bd;font-size:12px}
    #human-engine-panel .coach-dot {width:7px;height:7px;border-radius:50%;background:#809387;flex:none}
    #human-engine-panel[data-state=ready] .coach-dot {background:#36d5a7;box-shadow:0 0 8px #36d5a744}
    #human-engine-panel .coach-recommendation {display:flex;align-items:baseline;justify-content:space-between;padding:10px 12px;
      border:1px solid #384d41;border-radius:9px;background:#15221b;margin-bottom:14px;min-height:50px;gap:8px}
    #human-engine-panel [data-field=move] {font-size:24px;line-height:1.1;font-weight:750;color:#8ce4bc}
    #human-engine-panel [data-field=detail] {font-size:11px;color:#9cad9f;text-align:right}
    #human-engine-panel .coach-field {display:flex;flex-direction:column;gap:5px;color:#b8c9bf;font-size:11px;min-width:0}
    #human-engine-panel select {width:100%;height:33px;padding:0 8px;border:1px solid #465b4d;
      border-radius:7px;background:#17241c;color:#eef4ef;font:12px system-ui,sans-serif;appearance:auto}
    #human-engine-panel .coach-levels {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:7px 0 14px}
    #human-engine-panel .coach-level {border:1px solid #465b4d;border-radius:8px;background:#17241c;color:#c4d1c8;
      min-height:44px;padding:6px 2px;font:650 12px system-ui;cursor:pointer}
    #human-engine-panel .coach-level small {display:block;font-size:10px;font-weight:600;color:#9cad9f;margin-top:2px}
    #human-engine-panel .coach-level[aria-pressed=true] {color:#102a20;background:#7ee1b5;border-color:#a2efcf}
    #human-engine-panel .coach-level[aria-pressed=true] small {color:#2c5545}
    #human-engine-panel .coach-appearance {display:flex;align-items:center;gap:8px;margin-top:13px;padding-top:12px;border-top:1px solid #34463b}
    #human-engine-panel .coach-appearance label {display:flex;align-items:center;gap:6px;font-size:11px;color:#b8c9bf}
    #human-engine-panel input[type=color] {width:26px;height:25px;padding:1px;border:1px solid #526b59;border-radius:5px;background:none;cursor:pointer}
    #human-engine-panel input[type=range] {min-width:40px;width:70px;accent-color:#4dd5a5;margin:0}
    #human-engine-panel .coach-footer {font-size:10px;color:#859c8d;margin:10px 0 0}
  `;
  document.head.appendChild(style);
  const panel = document.createElement('section');
  panel.id = 'human-engine-panel';
  panel.setAttribute('aria-label', 'Move Coach');
  panel.innerHTML = `
    <div class="coach-head">
      <div><div class="coach-eyebrow">MOVE COACH</div><h2 data-field="engine-name">PATRICIA</h2></div>
      <div style="display:flex;align-items:center;gap:8px">
        <button type="button" class="coach-collapse" data-action="collapse" aria-label="Ciutkan panel">▾</button>
        <label class="coach-switch"><input type="checkbox" aria-label="Aktif"><span>Aktif</span></label>
      </div>
    </div>
    <div data-body>
      <div class="coach-status"><span class="coach-dot"></span><span data-field="status">Menyiapkan rekomendasi…</span></div>
      <div class="coach-recommendation"><span data-field="move">—</span><span data-field="detail"></span></div>
      <div id="coach-elo-label" class="coach-eyebrow">SKILL LEVEL PATRICIA</div>
      <div class="coach-levels" role="group" aria-labelledby="coach-elo-label"></div>
      <label class="coach-field">Saya bermain<select aria-label="Warna pemain"><option value="auto">Otomatis</option><option value="white">Putih</option><option value="black">Hitam</option><option value="both">Kedua sisi · analisis</option></select></label>
      <div class="coach-appearance"><label>Warna<input type="color" aria-label="Warna panah"></label>
        <label style="margin-left:auto">Tebal<input type="range" aria-label="Ketebalan panah" min="6" max="26" step="1"><span data-field="width"></span></label></div>
      <p class="coach-footer" data-field="footer">Rekomendasi panah saat giliranmu · tanpa gerak otomatis</p>
    </div>
  `;
  const buttons = new Map();
  for (const {skill, elo} of levels) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'coach-level';
    button.dataset.skill = String(skill);
    button.innerHTML = `Skill ${skill}<small>≈${elo}</small>`;
    button.addEventListener('click', () => save({skill}));
    panel.querySelector('.coach-levels').appendChild(button);
    buttons.set(skill, button);
  }
  const text = (field, value) => { const node = panel.querySelector(`[data-field="${field}"]`); if (node) node.textContent = value; };
  function save(change) {
    const relevant = ['enabled', 'skill', 'side'].some(key => key in change && change[key] !== prefs[key]);
    prefs = clean({...prefs, ...change});
    if (relevant) { revision++; lastMove = null; }
    try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch {}
    tick();
  }
  panel.querySelector('[aria-label="Aktif"]').addEventListener('change', e => save({enabled: e.target.checked}));
  panel.querySelector('[aria-label="Warna pemain"]').addEventListener('change', e => save({side: e.target.value}));
  panel.querySelector('[aria-label="Warna panah"]').addEventListener('input', e => save({color: e.target.value}));
  panel.querySelector('[aria-label="Ketebalan panah"]').addEventListener('input', e => save({width: Number(e.target.value)}));
  panel.querySelector('[data-action="collapse"]').addEventListener('click', () => save({collapsed: !prefs.collapsed}));
  function mount() {
    const sidebar = document.querySelector('#board-layout-sidebar');
    if (sidebar && panel.parentNode !== sidebar) { sidebar.prepend(panel); return; }
    const board = document.querySelector(boardSelector);
    if (board?.parentNode && panel.parentNode !== board.parentNode) board.parentNode.insertBefore(panel, board);
  }
  function fromAPI(value) {
    if ([1, 'white', 'w'].includes(value)) return 'white';
    if ([2, 'black', 'b'].includes(value)) return 'black';
    return null;
  }
  function identityColor(headers) {
    const white = String(headers.White || '').toLowerCase(), black = String(headers.Black || '').toLowerCase();
    const matches = new Set();
    for (const link of document.querySelectorAll('a.sidebar-link[href*="/member/"], a.nav-link-user[href*="/member/"], #navigation a[href*="/member/"]')) {
      try {
        const name = decodeURIComponent(new URL(link.href, location.href).pathname.split('/member/')[1] || '').replace(/\/$/, '').toLowerCase();
        if (name && name === white) matches.add('white');
        if (name && name === black) matches.add('black');
      } catch {}
    }
    return matches.size === 1 ? [...matches][0] : null;
  }
  function snapshot() {
    const board = document.querySelector(boardSelector), g = board?.game;
    if (!g) return null;
    const fen = g.getFEN(), turn = fen.split(' ')[1] === 'w' ? 'white' : 'black';
    const headers = g.getHeaders?.() || {};
    const mode = board.state?.mode || g.getMode?.()?.name || '';
    const result = g.getResult?.() || headers.Result || '*';
    const atEnd = g.isAtEndOfLine?.() !== false;
    const online = /^\/game\//.test(location.pathname);
    const playerColor = fromAPI(g.getPlayingAs?.()) || fromAPI(board.state?.playingAs) || identityColor(headers);
    let phase = 'playing';
    if (result !== '*' && atEnd) phase = 'ended';
    else if (result !== '*' && !atEnd) phase = 'review';
    else if (!atEnd) phase = 'history';
    else if (!online && mode !== 'playing') phase = 'idle';
    const plies = g.getSelectedNode?.()?.ply || ((Number(fen.split(' ')[5]) - 1) * 2 + (turn === 'black' ? 1 : 0));
    if (lastGame !== g || (phase === 'playing' && atEnd && (plies < lastPlies || lastResult !== '*'))) gameEpoch++;
    lastGame = g; lastResult = result;
    if (phase === 'playing' && atEnd) lastPlies = plies;
    const side = prefs.side === 'white' || prefs.side === 'black' ? prefs.side : playerColor;
    let reason = 'ready';
    if (!prefs.enabled) reason = 'disabled';
    else if (phase === 'ended') reason = 'ended';
    else if (phase === 'idle') reason = 'idle';
    else if (phase === 'history' && prefs.side !== 'both') reason = 'history';
    else if (phase !== 'review' && prefs.side !== 'both' && !side) reason = 'unknown';
    else if (phase !== 'review' && prefs.side !== 'both' && turn !== side) reason = 'opponent';
    const gameId = `${location.pathname}:${instanceId}:${gameEpoch}`;
    const token = JSON.stringify([gameId, fen, phase, side, reason, revision]);
    return {fen, turn, playerColor, side, phase, reason, eligible: reason === 'ready',
      gameId, token, revision, prefs: {...prefs}};
  }
  const STATUS = {ready: 'Giliranmu · rekomendasi Patricia', opponent: 'Menunggu langkah lawan',
    disabled: 'Nonaktif', ended: 'Game selesai', idle: 'Buka game untuk memulai',
    history: 'Mode riwayat · kembali ke posisi live', unknown: 'Menunggu identitas pemain',
    review: 'Mode analisis'};
  function tick() {
    if (!alive) return null;
    mount();
    const s = snapshot();
    panel.querySelector('[aria-label="Aktif"]').checked = prefs.enabled;
    panel.querySelector('.coach-switch span').textContent = prefs.enabled ? 'Aktif' : 'Nonaktif';
    panel.querySelector('[aria-label="Warna pemain"]').value = prefs.side;
    panel.querySelector('[aria-label="Warna panah"]').value = prefs.color;
    panel.querySelector('[aria-label="Ketebalan panah"]').value = String(prefs.width);
    text('width', String(prefs.width));
    for (const [skill, button] of buttons) button.setAttribute('aria-pressed', String(skill === prefs.skill));
    panel.dataset.collapsed = String(prefs.collapsed);
    panel.querySelector('[data-body]').style.display = prefs.collapsed ? 'none' : '';
    panel.querySelector('[data-action="collapse"]').textContent = prefs.collapsed ? '▸' : '▾';
    text('engine-name', `SKILL ${prefs.skill} · ≈${eloBySkill.get(prefs.skill)}`);
    text('footer', `Patricia Skill Level ${prefs.skill} · estimasi engine ≈${eloBySkill.get(prefs.skill)} · bukan rating resmi`);
    if (!s) { text('status', 'Menunggu papan…'); return null; }
    panel.dataset.state = s.reason;
    text('status', STATUS[s.reason] || s.reason);
    if (lastMove && lastMove.token === s.token) {
      text('move', String(lastMove.san || lastMove.move || '—').toUpperCase());
      text('detail', `Patricia · Skill ${prefs.skill}`);
    } else {
      text('move', '—');
      text('detail', s.eligible ? 'Menyiapkan…' : '');
      if (!s.eligible) document.querySelectorAll('#human-engine-arrow').forEach(e => e.remove());
    }
    return s;
  }
  const api = {
    version: VERSION,
    read() { return tick(); },
    poll() { return tick(); },
    report(payload) {
      const current = tick();
      if (!current?.eligible || payload.token !== current.token || payload.skill !== prefs.skill) return false;
      lastMove = payload;
      tick();
      return true;
    },
    destroy() {
      alive = false;
      document.querySelectorAll('#human-engine-arrow').forEach(e => e.remove());
      panel.remove();
      style.remove();
      delete window[GLOBAL];
    }
  };
  window[GLOBAL] = api;
  return tick();
}
