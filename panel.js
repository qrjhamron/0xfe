({defaults, presets, configId}) => {
  const VERSION = 12;
  const GLOBAL = '__chessArrowCoach';
  if (window[GLOBAL]?.version === VERSION && window[GLOBAL]?.configId === configId) return window[GLOBAL].read();
  window[GLOBAL]?.destroy();
  const boardSelector = 'wc-chess-board, chess-board';
  const firstBoard = document.querySelector(boardSelector);
  if (!firstBoard?.game) return null;
  const KEY = 'chess-arrow-coach-v2';
  const choices=presets;
  const levels=Object.keys(choices).map(Number).sort((a,b)=>a-b);
  const initial = {enabled:true, elo:defaults.elo||1500, color:'#20c4a0', width:14,
    autoMove:false, autoPremove:false, timeManagement:true, adaptiveDelay:true, adaptiveStrength:true, endgamePremove:true, advancedPremove:true, panelCollapsed:false, premoveLimit:1, delay:1200, cursorMs:400, side:defaults.bothSides ? 'both' : 'auto'};
  const clean = value => {
    const wanted=Number(value?.elo)||initial.elo;
    const available=levels.filter(elo=>choices[elo].available);
    // Preserve unavailable levels visibly rather than silently changing strength.
    const elo=levels.includes(wanted)?wanted:
      (available.includes(initial.elo)?initial.elo:available[0]||initial.elo);
    return {
      elo, autoMove:aliveAutomation && value?.autoMove===true, autoPremove:alivePremove && value?.autoPremove===true,
      timeManagement:value?.timeManagement!==false, adaptiveDelay:value?.adaptiveDelay!==false,
      adaptiveStrength:value?.adaptiveStrength!==false,
      endgamePremove:value?.endgamePremove!==false, advancedPremove:value?.advancedPremove!==false, premoveLimit:1,
      panelCollapsed:value?.panelCollapsed===true,
      premoveBreadth:[3,5,8].includes(Number(value?.premoveBreadth))?Number(value.premoveBreadth):5,
      premovePolicy:['strict','balanced','active'].includes(value?.premovePolicy)?value.premovePolicy:'balanced',
      delay:Math.min(10000,Math.max(0,Number.isFinite(Number(value?.delay))&&value?.delay!=null?Number(value.delay):1200)),
      cursorMs:Math.min(600,Math.max(60,Number(value?.cursorMs)||400)),
      enabled:typeof value?.enabled==='boolean'?value.enabled:initial.enabled,
      color:/^#[a-f0-9]{6}$/i.test(value?.color||'')?value.color:initial.color,
      width:Math.min(26,Math.max(6,Number(value?.width)||initial.width)),
      side:['auto','white','black','both'].includes(value?.side)?value.side:initial.side
    };
  };
  let alivePremove=false;
  let aliveAutomation=false; // Reloads always disarm automation.
  let queuedMove=null;
  let nativeOwned=null,nativeRejected='',nativeRetryAt=0,nativeRetries=0,lastNativeSupported=false;
  let auditGame='',auditSequence=0,auditEvents=[],auditCounts={queued:0,used:0,observed:0,cancelled:0,rejected:0};
  let listenerGame=null,listenerHandler=null,branchState=null,branchSignature='';
  let prefs;
  try { prefs = clean(JSON.parse(localStorage.getItem(KEY))); } catch { prefs = clean(null); }
  let revision = 0;
  let alive = true;
  let lastEligibility = '';
  let lastMove = null;
  let backendState=null,validationError='';
  let lastHeartbeat=Date.now();
  const instanceId=crypto.randomUUID?.()||String(Date.now()+Math.random());
  let lastGame=null,gameEpoch=0,lastPlies=0,lastResult='*';
  let historyToken='',historyData={};
  const style = document.createElement('style');
  style.id = 'human-engine-panel-style';
  style.textContent = `
    #human-engine-panel {box-sizing:border-box;width:100%;margin:0 0 14px;padding:16px;
      background:linear-gradient(145deg,#23312b,#1b2420);color:#f2f5f3;border:1px solid #3b4b42;
      border-radius:14px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 6px 20px #0002;text-align:left}
    #human-engine-panel * {box-sizing:border-box}
    #human-engine-panel .coach-head {display:flex;align-items:center;justify-content:space-between;gap:12px}
    #human-engine-panel[data-collapsed=true] {padding-bottom:11px}
    #human-engine-panel .coach-head-actions {display:flex;align-items:center;gap:8px}
    #human-engine-panel .coach-collapse {width:30px;height:28px;padding:0;border:1px solid #465b4d;border-radius:7px;background:#17241c;color:#c4d1c8;font:700 16px/1 system-ui;cursor:pointer}
    #human-engine-panel .coach-collapse:hover {background:#2b4435;border-color:#76a88a}
    #human-engine-panel .coach-collapse:focus-visible {outline:2px solid #a2efcf;outline-offset:2px}
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
    #human-engine-panel .coach-settings {display:grid;grid-template-columns:1fr 1fr;gap:12px}
    #human-engine-panel .coach-field {display:flex;flex-direction:column;gap:5px;color:#b8c9bf;font-size:11px;min-width:0}
    #human-engine-panel select,#human-engine-panel input[type=number] {width:100%;height:33px;padding:0 8px;border:1px solid #465b4d;
      border-radius:7px;background:#17241c;color:#eef4ef;font:12px system-ui,sans-serif;appearance:auto}
    #human-engine-panel select:focus-visible,#human-engine-panel input:focus-visible {outline:2px solid #6cdeb0;outline-offset:2px}
    #human-engine-panel .coach-levels {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:7px 0 14px}
    #human-engine-panel .coach-level {border:1px solid #465b4d;border-radius:8px;background:#17241c;color:#c4d1c8;
      min-height:36px;padding:7px 2px;font:650 12px system-ui;cursor:pointer;transition:background .12s,border-color .12s}
    #human-engine-panel .coach-level:hover {background:#2b4435;border-color:#76a88a}
    #human-engine-panel .coach-level[aria-pressed=true] {color:#102a20;background:#7ee1b5;border-color:#a2efcf}
    #human-engine-panel .coach-level:focus-visible {outline:2px solid #a2efcf;outline-offset:2px}
    #human-engine-panel .coach-level:disabled {opacity:.35;cursor:not-allowed}
    #human-engine-panel .coach-appearance {display:flex;align-items:center;gap:8px;margin-top:13px;padding-top:12px;border-top:1px solid #34463b}
    #human-engine-panel .coach-appearance label {display:flex;align-items:center;gap:6px;font-size:11px;color:#b8c9bf}
    #human-engine-panel input[type=color] {width:26px;height:25px;padding:1px;border:1px solid #526b59;border-radius:5px;background:none;cursor:pointer}
    #human-engine-panel input[type=range] {min-width:40px;width:70px;accent-color:#4dd5a5;margin:0}
    #human-engine-panel .coach-footer {font-size:10px;color:#859c8d;margin:10px 0 0}
    #human-engine-panel [data-field=error] {color:#f0b482;font-size:11px;margin:8px 0 0;min-height:0}
    #human-engine-panel [data-field=error]:empty {display:none}
  `;
  document.head.appendChild(style);
  const panel = document.createElement('section');
  panel.id = 'human-engine-panel';
  panel.setAttribute('aria-label','Kontrol panah');
  panel.innerHTML = `
    <div class="coach-head"><div><div class="coach-eyebrow" data-field="engine-name">LEVEL LATIHAN · GUEST</div><h2>Move Coach</h2></div>
      <div class="coach-head-actions"><button type="button" class="coach-collapse" data-action="collapse" aria-label="Tutup panel" aria-expanded="true">⌃</button>
      <label class="coach-switch"><input type="checkbox" aria-label="Panah aktif"><span>Aktif</span></label></div></div>
    <div class="coach-status" role="status" aria-live="polite"><span class="coach-dot"></span><span data-field="status">Membaca posisi…</span></div>
    <div class="coach-recommendation"><strong data-field="move">—</strong><span data-field="detail">Menunggu posisi</span></div>
    <div class="coach-field" id="coach-elo-label">Pilih Elo</div>
    <div class="coach-levels" role="group" aria-labelledby="coach-elo-label"></div>
    <div class="coach-settings" style="grid-template-columns:1fr">
      <label class="coach-field">Saya bermain<select aria-label="Warna pemain"><option value="auto">Otomatis</option><option value="white">Putih</option><option value="black">Hitam</option><option value="both">Kedua sisi · analisis</option></select></label>
    </div>
    <div style="margin-top:12px" class="coach-settings">
      <label class="coach-switch"><input type="checkbox" aria-label="Auto move">Auto move</label>
      <label class="coach-field">Delay (ms)<input type="number" aria-label="Delay auto move" min="0" max="10000" step="50" value="1200"></label>
    <label class="coach-switch"><input type="checkbox" aria-label="Time management">Time management</label>
    <label class="coach-switch"><input type="checkbox" aria-label="Adaptive auto move delay">Adaptive delay</label>
    <label class="coach-switch"><input type="checkbox" aria-label="Adaptive engine strength">Kekuatan adaptif per fase</label>
    <label class="coach-switch"><input type="checkbox" aria-label="Endgame premove">Endgame premove</label>
    <label class="coach-switch"><input type="checkbox" aria-label="Advanced premove">Advanced premove</label>
      <label class="coach-switch"><input type="checkbox" aria-label="Auto premove">Auto premove</label>
      <span class="coach-field">Antrean: 1 langkah · isi ulang tiap giliran</span>
      <label class="coach-field">Cabang lawan<select aria-label="Cabang premove"><option value="3">3 cabang · ringan</option><option value="5">5 cabang · seimbang</option><option value="8">8 cabang · luas</option></select></label>
      <label class="coach-field">Pola premove<select aria-label="Pola premove"><option value="strict">Ketat</option><option value="balanced">Seimbang</option><option value="active">Aktif</option></select></label>
      <label class="coach-field">Gerak kursor (ms)<input type="number" aria-label="Durasi kursor" min="60" max="600" step="20" value="400"></label>
      <button type="button" data-action="stop">Stop · Esc</button>
      <span data-field="automation" role="status">Otomatis mati</span>
    </div>
    <div class="coach-footer" data-field="native-status"></div>
    <button type="button" data-action="site-premove" hidden>Buka pengaturan premove Chess.com</button>
    <p class="coach-footer" data-field="premove-stats">Terpasang 0 · terpakai 0 · batal 0</p>
    <details><summary>Cabang balasan</summary><div data-field="premove-plan">Aktifkan Auto premove untuk membaca cabang.</div></details>
    <div class="coach-appearance"><label>Warna<input type="color" aria-label="Warna panah"></label>
      <label style="margin-left:auto">Tebal<input type="range" aria-label="Ketebalan panah" min="6" max="26" step="1"><span data-field="width"></span></label></div>
    <p data-field="error" role="alert"></p><p class="coach-footer" data-field="footer">Elo perkiraan · rekomendasi saat giliranmu</p>
  `;
  const head = panel.firstElementChild;
  const body = document.createElement('div');
  body.className = 'coach-body';
  while (panel.children.length > 1) body.append(panel.children[1]);
  panel.append(body);
  const input = {
    enabled:panel.querySelector('[aria-label="Panah aktif"]'),
    side:panel.querySelector('[aria-label="Warna pemain"]'), color:panel.querySelector('[aria-label="Warna panah"]'),
    width:panel.querySelector('[aria-label="Ketebalan panah"]')
  };
  const buttons=new Map();
  for (const elo of levels) {
    const button=document.createElement('button');button.type='button';
    button.className='coach-level';button.textContent=String(elo);
    button.setAttribute('aria-label',`Elo ${elo}`);button.setAttribute('aria-pressed','false');
    button.disabled=!choices[elo].available;
    const evidence=choices[elo];
    button.title=button.disabled?'Level belum tersedia':
      `Target ${elo} · estimasi lokal ${evidence.estimate} · rentang sampel 95% ${evidence.interval[0]}–${evidence.interval[1]} (${evidence.games} game)${evidence.target_within_interval?'':' · target masih tentatif'}`;
    button.addEventListener('click',()=>save({elo}));
    panel.querySelector('.coach-levels').appendChild(button);buttons.set(elo,button);
  }
  const field = name => panel.querySelector(`[data-field="${name}"]`);
  const text = (name,value) => { if (field(name).textContent !== value) field(name).textContent=value; };
  function syncInputs() {
    for (const [elo,button] of buttons) button.setAttribute('aria-pressed',String(elo===prefs.elo));
    panel.querySelector('[aria-label="Auto move"]').checked=prefs.autoMove;
    panel.querySelector('[aria-label="Delay auto move"]').value=String(prefs.delay);
    panel.querySelector('[aria-label="Time management"]').checked=prefs.timeManagement;
    panel.querySelector('[aria-label="Adaptive auto move delay"]').checked=prefs.adaptiveDelay;
    panel.querySelector('[aria-label="Adaptive engine strength"]').checked=prefs.adaptiveStrength;
    panel.querySelector('[aria-label="Endgame premove"]').checked=prefs.endgamePremove;
    panel.querySelector('[aria-label="Advanced premove"]').checked=prefs.advancedPremove;
    panel.querySelector('[aria-label="Auto premove"]').checked=prefs.autoPremove;
    panel.querySelector('[aria-label="Durasi kursor"]').value=String(prefs.cursorMs);
    panel.querySelector('[aria-label="Cabang premove"]').value=String(prefs.premoveBreadth);
    panel.querySelector('[aria-label="Pola premove"]').value=prefs.premovePolicy;
    input.enabled.checked=prefs.enabled;input.side.value=prefs.side;
    input.color.value=prefs.color; input.width.value=String(prefs.width);
    body.hidden=prefs.panelCollapsed;
    panel.dataset.collapsed=String(prefs.panelCollapsed);
    const collapse=panel.querySelector('[data-action="collapse"]');
    collapse.setAttribute('aria-expanded',String(!prefs.panelCollapsed));
    collapse.setAttribute('aria-label',prefs.panelCollapsed?'Buka panel':'Tutup panel');
    collapse.textContent=prefs.panelCollapsed?'⌄':'⌃';
    text('width',String(prefs.width));
    panel.querySelector('.coach-switch span').textContent=prefs.enabled ? 'Aktif' : 'Nonaktif';
    text('engine-name',`LEVEL ${prefs.elo} · GUEST`);
    const evidence=choices[prefs.elo];
    text('footer',`${evidence.target_within_interval?'Level latihan':'Target tentatif'} · estimasi lokal ≈${Math.round(evidence.estimate/10)*10}`);
  }
  function clearArrow() { document.querySelectorAll('#human-engine-arrow').forEach(e=>e.remove()); }
  function save(change) {
    if(change.enabled===false||('side' in change&&change.side!==prefs.side))queuedMove=null;
    if(Object.keys(change).some(k=>['enabled','elo','side','autoPremove','premoveBreadth','premovePolicy','adaptiveStrength','endgamePremove','advancedPremove'].includes(k)))cancelNative('settings');
    prefs=clean({...prefs,...change});
    if (Object.keys(change).some(key=>['enabled','elo','side','autoMove','autoPremove','timeManagement','adaptiveDelay','adaptiveStrength','endgamePremove','advancedPremove','premoveBreadth','premovePolicy','delay','cursorMs'].includes(key))) {
      revision++; lastMove=null; backendState=null; clearArrow();
    }
    validationError='';
    try { localStorage.setItem(KEY,JSON.stringify(prefs)); } catch {}
    syncInputs(); tick();
  }
  input.enabled.addEventListener('change',()=>save({enabled:input.enabled.checked}));
  input.side.addEventListener('change',()=>save({side:input.side.value}));
  input.color.addEventListener('input',()=>save({color:input.color.value}));
  input.width.addEventListener('input',()=>save({width:Number(input.width.value)}));
  function stopAutomation() {
    cancelNative();aliveAutomation=false;alivePremove=false;queuedMove=null;save({autoMove:false,autoPremove:false});
    text('automation','Otomatis dihentikan');
  }
  panel.querySelector('[aria-label="Auto move"]').addEventListener('change',e=>{
    aliveAutomation=e.target.checked;save({autoMove:e.target.checked});
    text('automation',prefs.autoMove?'Auto move aktif':'Otomatis mati');
  });
  panel.querySelector('[aria-label="Delay auto move"]').addEventListener('change',e=>save({delay:Number(e.target.value)}));
  panel.querySelector('[aria-label="Time management"]').addEventListener('change',e=>save({timeManagement:e.target.checked}));
  panel.querySelector('[aria-label="Adaptive auto move delay"]').addEventListener('change',e=>save({adaptiveDelay:e.target.checked}));
  panel.querySelector('[aria-label="Adaptive engine strength"]').addEventListener('change',e=>save({adaptiveStrength:e.target.checked}));
  panel.querySelector('[data-action="collapse"]').addEventListener('click',()=>save({panelCollapsed:!prefs.panelCollapsed}));
  panel.querySelector('[aria-label="Endgame premove"]').addEventListener('change',e=>save({endgamePremove:e.target.checked}));
  panel.querySelector('[aria-label="Advanced premove"]').addEventListener('change',e=>save({advancedPremove:e.target.checked}));
  panel.querySelector('[data-action="stop"]').addEventListener('click',stopAutomation);
  panel.querySelector('[aria-label="Auto premove"]').addEventListener('change',e=>{
    alivePremove=e.target.checked;save({autoPremove:e.target.checked});
    text('automation',prefs.autoPremove?'Auto premove aktif · memprediksi balasan lawan':'Auto premove mati');
  });
  panel.querySelector('[aria-label="Durasi kursor"]').addEventListener('change',e=>save({cursorMs:Number(e.target.value)}));
  panel.querySelector('[aria-label="Cabang premove"]').addEventListener('change',e=>save({premoveBreadth:Number(e.target.value)}));
  panel.querySelector('[aria-label="Pola premove"]').addEventListener('change',e=>save({premovePolicy:e.target.value}));
  panel.querySelector('[data-action="site-premove"]').addEventListener('click',()=>{
    const gameSettings=[...document.querySelectorAll('button[aria-label="Settings"]')].find(e=>e.id!=='board-controls-settings');
    (gameSettings||document.querySelector('#board-controls-settings'))?.click();
  });
  function escape(event) {if(event.key==='Escape')stopAutomation();}
  window.addEventListener('keydown',escape);
  function fromAPI(value) {
    if ([1,'white','w'].includes(value)) return 'white';
    if ([2,'black','b'].includes(value)) return 'black';
    return null;
  }
  function identityColor(headers) {
    const white=String(headers.White||'').toLowerCase(), black=String(headers.Black||'').toLowerCase();
    const matches=new Set();
    // Navigation identifies the local Guest; player cards can move when the board flips.
    for (const link of document.querySelectorAll('a.sidebar-link[href*="/member/"], a.nav-link-user[href*="/member/"], #navigation a[href*="/member/"]')) {
      try {
        const name=decodeURIComponent(new URL(link.href,location.href).pathname.split('/member/')[1]||'').replace(/\/$/,'').toLowerCase();
        if (name&&name===white) matches.add('white');
        if (name&&name===black) matches.add('black');
      } catch {}
    }
    return matches.size===1 ? [...matches][0] : null;
  }
  function snapshot() {
    const board=document.querySelector(boardSelector), g=board?.game;
    if (!g) return null;
    const fen=g.getFEN(), turn=fen.split(' ')[1]==='w'?'white':'black';
    const headers=g.getHeaders?.()||{};
    const options=g.getOptions?.()||{};
    const mode=board.state?.mode||g.getMode?.()?.name||'';
    const result=g.getResult?.()||headers.Result||'*';
    const atEnd=g.isAtEndOfLine?.()!==false;
    const online=/^\/game\//.test(location.pathname);
    const playerColor=fromAPI(g.getPlayingAs?.())||fromAPI(board.state?.playingAs)||identityColor(headers);
    let phase='playing';
    if (result!=='*'&&atEnd) phase='ended';
    else if (result!=='*'&&!atEnd) phase='review';
    else if (!atEnd) phase='history';
    else if (!online&&mode!=='playing') phase='idle';
    const clockValue=(selector)=>{const e=document.querySelector(selector);if(!e)return null;const t=(e.innerText||e.textContent||'').trim();const m=t.match(/^(?:(\d+):)?(\d+)(?:\.(\d+))?$/);if(!m)return null;return ((Number(m[1]||0)*60)+Number(m[2]||0))*1000+Number((m[3]||'0').padEnd(3,'0').slice(0,3));};
    const clocks={white:clockValue('.clock-bottom.clock-white'),black:clockValue('.clock-top.clock-black')};
    const plies=g.getSelectedNode?.()?.ply||((Number(fen.split(' ')[5])-1)*2+(turn==='black'?1:0));
    if (lastGame!==g||(phase==='playing'&&atEnd&&(plies<lastPlies||lastResult!=='*'))) gameEpoch++;
    lastGame=g;lastResult=result;
    if (phase==='playing'&&atEnd) lastPlies=plies;
    const side=prefs.side==='white'||prefs.side==='black'?prefs.side:playerColor;
    let reason='ready';
    if (!prefs.enabled) reason='disabled';
    else if (Date.now()-lastHeartbeat>4500) reason='disconnected';
    else if (!choices[prefs.elo]?.available) reason='unavailable';
    else if (phase==='ended') reason='ended';
    else if (phase==='idle') reason='idle';
    else if (phase==='history'&&prefs.side!=='both') reason='history';
    else if (phase!=='review'&&prefs.side!=='both'&&!side) reason='unknown';
    else if (phase!=='review'&&prefs.side!=='both'&&turn!==side) reason='opponent';
    const gameId=`${location.pathname}:${instanceId}:${gameEpoch}`;
    if (queuedMove&&(queuedMove.gameId!==gameId||phase!=='playing'||(turn!==side&&queuedMove.fen!==fen))) queuedMove=null;
    const token=JSON.stringify([gameId,fen,phase,side,reason,revision]);
    return {fen,turn,playerColor,side,phase,reason,eligible:reason==='ready',mode,clocks,
      flipped:!!options.flipped,atEnd,result,revision,token,gameId,prefs:{...prefs},queuedMove:queuedMove?.move||null};
  }
  function nativeState() {
    const g=document.querySelector(boardSelector)?.game,p=g?.premoves;
    try {return {supported:typeof p?.move==='function'&&typeof p?.getQueue==='function'&&typeof p?.cancel==='function',
      owned:!!nativeOwned,queue:(p?.getQueue?.()||[]).map(m=>m.from+m.to+(m.promotion||''))};}
    catch{return {supported:false,owned:false,queue:[]};}
  }
  function audit(kind,extra={}) {
    if(kind in auditCounts)auditCounts[kind]++;
    auditEvents.push({id:++auditSequence,gameId:auditGame,time:Date.now(),kind,...extra});
    if(auditEvents.length>96)auditEvents.shift();
  }
  function bindNativeEvents(g) {
    if(g===listenerGame)return;
    if(listenerGame&&listenerHandler)try{listenerGame.offAll?.(listenerHandler);}catch{}
    listenerGame=g;
    listenerHandler=event=>{
      const v=event?.data||event;
      if(event?.consumedPremove!==true&&v?.consumedPremove!==true)return;
      if(!nativeOwned?.confirmed||nativeOwned.game!==g||nativeOwned.gameId!==auditGame)return;
      const m=v?.move||event?.move;
      const move=m?.from&&m?.to?m.from+m.to+(m.promotion||''):null;
      if(move!==nativeOwned.move||!nativeOwned.after.has(g.getFEN()))return;
      audit('used',{move,base:nativeOwned.base,source:'native-event'});
      nativeOwned=null;
    };
    g.onAll?.(listenerHandler);
  }
  function sitePremoveSetting() {
    try {
      const direct=JSON.parse(localStorage.getItem('json_settings')||'{}');
      if(typeof direct['gameplay.live.premoves']==='boolean')return direct['gameplay.live.premoves'];
      const cache=JSON.parse(localStorage.getItem('settingsHttpCache')||'{}');
      for(const groups of Object.values(cache))for(const value of Object.values(groups||{})){
        const flag=value?.settings?.['gameplay.live.premoves'];
        if(typeof flag==='boolean')return flag;
      }
    }catch{}
    return null;
  }
  function cancelNative(reason='stop') {
    if(nativeOwned){
      const owned=nativeOwned;nativeOwned=null;
      try{owned.game.premoves?.cancel();}catch{}
      if(owned.confirmed)audit('cancelled',{move:owned.move,base:owned.base,reason});
    }
    nativeOwned=null;
  }
  function queueNative(payload) {
    const s=tick(),g=document.querySelector(boardSelector)?.game,n=nativeState();
    if(!s||s.phase!=='playing'||s.reason!=='opponent'||!prefs.enabled||!prefs.autoPremove||
       prefs.side==='both'||payload.token!==s.token||payload.base!==s.fen||!n.supported)return false;
    if(nativeRejected!==s.token)nativeRetries=0;
    if(nativeRejected===s.token&&(nativeRetries>=2||Date.now()<nativeRetryAt))return false;
    const plan=payload.plan;
    if(!Array.isArray(plan)||plan.length!==1)return false;
    if(plan.some(x=>! /^[a-h][1-8][a-h][1-8][qrbn]?$/.test(x.move)))return false;
    if(n.queue.length&&!nativeOwned)return false; // Respect manually entered premoves.
    const moves=plan.map(x=>x.move);
    if(nativeOwned&&JSON.stringify(n.queue)===JSON.stringify(moves))return true;
    if(nativeOwned)return false; // Keep a queued choice stable for this opponent turn.
    nativeOwned={gameId:s.gameId,game:g,base:s.fen,move:moves[0],
      states:new Set([s.fen,...plan.flatMap(x=>x.states||[x.before,x.after])]),
      after:new Set(plan[0].states?.filter((_,i)=>i%2===1)||[plan[0].after])};
    try {
      for(const item of plan){
        const move={from:item.move.slice(0,2),to:item.move.slice(2,4)};
        if(item.move.length===5)move.promotion=item.move[4];
        g.premoves.move(move);
      }
      if(g.getFEN()!==s.fen||JSON.stringify(nativeState().queue)!==JSON.stringify(moves)){
        nativeRejected=s.token;nativeRetries++;nativeRetryAt=Date.now()+1000;cancelNative('rejected');
        audit('rejected',{move:moves[0]});text('automation','Antrean native ditolak situs');return false;
      }
      nativeOwned.confirmed=true;
      audit('queued',{move:moves[0],base:s.fen,queue:nativeState().queue});
      text('automation','1 premove native · menunggu lawan');
      return true;
    }catch{nativeRejected=s.token;nativeRetries++;nativeRetryAt=Date.now()+1000;cancelNative('rejected');audit('rejected',{move:moves[0]});return false;}
  }
  function mount() {
    const sidebar=document.querySelector('#board-layout-sidebar');
    if (sidebar&&panel.parentNode!==sidebar) sidebar.prepend(panel);
  }
  function tick() {
    if (!alive) return null;
    mount();
    const s=snapshot();
    if (!s) { clearArrow();panel.hidden=true;return null; }
    panel.hidden=false;
    const game=document.querySelector(boardSelector).game;
    bindNativeEvents(game);
    if(auditGame!==s.gameId){
      cancelNative('new-game');auditGame=s.gameId;auditSequence=0;auditEvents=[];
      auditCounts={queued:0,used:0,observed:0,cancelled:0,rejected:0};
      branchState=null;branchSignature='';nativeRejected='';
      text('premove-plan','Aktifkan Auto premove untuk membaca cabang.');
    }
    s.native=nativeState();
    if(s.native.supported&&!lastNativeSupported){nativeRejected='';nativeRetries=0;}
    lastNativeSupported=s.native.supported;
    if(nativeOwned&&s.native.queue.length&&(s.native.queue.length!==1||s.native.queue[0]!==nativeOwned.move)){
      audit('cancelled',{move:nativeOwned.move,reason:'manual-queue-replaced'});nativeOwned=null;
    }
    if(nativeOwned&&s.native.queue.length===0){
      if(nativeOwned.after.has(s.fen)){
        audit('observed',{move:nativeOwned.move,base:nativeOwned.base,source:'queue-and-fen'});nativeOwned=null;
      }else if(s.fen!==nativeOwned.base||!s.native.supported)cancelNative('queue-cleared');
    }
    if(nativeOwned&&(!prefs.autoPremove||!prefs.enabled||s.phase!=='playing'||s.gameId!==nativeOwned.gameId||!nativeOwned.states.has(s.fen)))cancelNative('position-changed');
    s.native=nativeState();
    s.premoveAudit={gameId:auditGame,...auditCounts};
    const siteSetting=sitePremoveSetting();
    const missing=prefs.autoPremove&&s.phase==='playing'&&!s.native.supported;
    const settingOff=prefs.autoPremove&&siteSetting===false;
    text('native-status',settingOff?'Enable Premoves Chess.com OFF · aktifkan di pengaturan papan':missing?'API premove belum tersedia · respons cabang tetap disiapkan':s.native.supported?'API premove native siap':'');
    panel.querySelector('[data-action="site-premove"]').hidden=!missing&&!settingOff;
    text('premove-stats',`Terpasang ${auditCounts.queued} · terpakai ${auditCounts.used} · teramati ${auditCounts.observed} · batal ${auditCounts.cancelled}`);
    if(prefs.autoPremove&&s.phase==='playing'){
      if(!s.native.supported)text('automation','Native premove tidak tersedia · menunggu giliran untuk Auto move');
      else if(s.native.owned&&s.native.queue.length)text('automation','1 premove native · antrean situs');
      else if(branchState?.base===s.fen||branchState?.base===s.fen.replace(/ ([a-h][36]) /,' - '))text('automation',branchState.message||'Menyiapkan premove');
    }
    if (lastEligibility!==s.token) { clearArrow();lastMove=null;backendState=null;lastEligibility=s.token; }
    const svg=document.querySelector('#human-engine-arrow');
    if (svg&&svg.dataset.flipped!==String(s.flipped)) clearArrow();
    else if (svg) {
      svg.querySelector('line').setAttribute('stroke',prefs.color);
      svg.querySelector('line').setAttribute('stroke-width',prefs.width);
      svg.querySelector('marker path').setAttribute('fill',prefs.color);
    }
    panel.dataset.state=s.reason;
    panel.dataset.playerColor=s.playerColor||'unknown';
    panel.dataset.turn=s.turn;
    const label=s.side==='white'?'Putih':s.side==='black'?'Hitam':'';
    const statuses={disabled:'Panah dinonaktifkan',disconnected:'Koneksi terputus · menunggu sambungan',unavailable:'Level belum tersedia',ended:'Permainan selesai',idle:'Siap saat permainan dimulai',
      history:'Melihat riwayat langkah',unknown:'Warna belum terdeteksi · pilih di bawah',opponent:`Giliran lawan · kamu ${label}`,
      ready:s.phase==='review'||prefs.side==='both'?`Analisis · ${s.turn==='white'?'Putih':'Hitam'} melangkah`:`Giliranmu · ${label}`};
    text('status',statuses[s.reason]);
    text('move',lastMove?.token===s.token?lastMove.san:'—');
    const phaseLabels={opening:'opening',middlegame:'middlegame',endgame:'endgame',tactical:'taktis',fixed:''};
    const phaseDetail=lastMove?.adaptive_strength&&phaseLabels[lastMove.phase]?` · ${phaseLabels[lastMove.phase]}`:'';
    text('detail',lastMove?.token===s.token?`${lastMove.move.slice(0,2)} → ${lastMove.move.slice(2,4)} · ${lastMove.cached?'cache':`${lastMove.latency_ms} ms`}${phaseDetail}`:
      s.eligible?(backendState?.message||'Mencari rekomendasi…'):s.reason==='opponent'?'Panah kembali saat giliranmu':'');
    text('error',validationError||backendState?.error||'');
    s.rendered=!!svg&&svg.dataset.token===s.token&&svg.dataset.flipped===String(s.flipped);
    return s;
  }
  function storage(event) {
    if (event.key!==KEY) return;
    try {
      const next=clean(JSON.parse(event.newValue));
      if (['enabled','elo','side'].some(key=>next[key]!==prefs[key])) {
        revision++;lastMove=null;backendState=null;clearArrow();
      }
      if(['enabled','elo','side','autoPremove','adaptiveStrength','endgamePremove','advancedPremove','premoveBreadth','premovePolicy'].some(k=>prefs[k]!==next[k]))cancelNative('settings');
      prefs={...next,autoMove:prefs.autoMove&&next.autoMove,autoPremove:prefs.autoPremove&&next.autoPremove};syncInputs();tick();
    } catch {}
  }
  window.addEventListener('storage',storage);
  syncInputs();
  let backgroundTick=0;
  const timer=setInterval(()=>{
    if (document.hidden&&Date.now()-backgroundTick<400) return;
    backgroundTick=Date.now();tick();
  },80);
  const api={version:VERSION, configId, read:tick,
    queueNative, cancelNative,
    audit:()=>({gameId:auditGame,counts:{...auditCounts},events:auditEvents.map(e=>({...e}))}),
    premoveState(payload) {
      const s=tick();
      if(!s||payload.token!==s.token)return false;
      const signature=JSON.stringify(payload);
      if(signature===branchSignature)return true;
      branchSignature=signature;branchState=payload;
      const target=field('premove-plan');target.replaceChildren();
      for(const branch of payload.branches||[]){
        const row=document.createElement('div');row.textContent=`${branch.opponent} → ${branch.reply||'…'}`;target.appendChild(row);
      }
      const note=document.createElement('p');
      const c=payload.coverage;
      note.textContent=c?.total?`${c.compatible}/${c.total} balasan lawan kompatibel · pemeriksaan terbatas`:payload.message||'';
      target.appendChild(note);tick();return true;
    },
    automationResult(message,consume=false) {
      if(consume)queuedMove=null;
      text('automation',message);
    },
    poll() {
      lastHeartbeat=Date.now();
      const s=tick();if (!s)return null;
      if (historyToken!==s.token) {
        const board=document.querySelector(boardSelector),g=board.game;
        const line=g.getCurrentFullLine?.()||[];
        historyData={rootFen:board.state?.startingFen||line[0]?.beforeFen||'',history:g.getHistorySANs?.()||[]};
        historyToken=s.token;
      }
      return {...s,...historyData};
    },
    progress(payload) {
      const current=tick();
      if (!current?.eligible||current.token!==payload.token) return false;
      backendState=payload;tick();return true;
    },
    report(payload) {
      const current=tick();
      if (!current||!current.eligible||payload.token!==current.token||payload.elo!==prefs.elo) return false;
      lastMove=payload;backendState=null;tick();return true;
    },
    destroy() {cancelNative('destroy');if(listenerGame&&listenerHandler)try{listenerGame.offAll?.(listenerHandler);}catch{}alive=false;clearInterval(timer);window.removeEventListener('storage',storage);window.removeEventListener('keydown',escape);document.querySelector('#coach-mouse')?.remove();clearArrow();panel.remove();style.remove();delete window[GLOBAL];}
  };
  window[GLOBAL]=api;
  return tick();
}
