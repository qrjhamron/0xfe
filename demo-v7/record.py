import sys,time,json
from pathlib import Path
sys.path.insert(0,'/workspace/chess-arrows')
import chess
from playwright.sync_api import sync_playwright
from check_browser import HTML
from auto_moves import AutoMoves
ROOT=Path('/workspace/chess-arrows');OUT=ROOT/'demo-v7'
data=json.loads((ROOT/'calibration-profiles.json').read_text())
print(list(data.keys()))
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':1120,'height':900},record_video_dir=str(OUT),record_video_size={'width':1120,'height':900})
 ctx.route('https://www.chess.com/game/demo-local',lambda r:r.fulfill(content_type='text/html',body=HTML))
 page=ctx.new_page();page.goto('https://www.chess.com/game/demo-local')
 page.add_style_tag(content='''body{margin:0;background:#151c19;color:#e9f1ea;font:16px system-ui}main{align-items:flex-start;margin:70px 40px!important;gap:36px!important}wc-chess-board{width:560px!important;height:560px!important;flex-shrink:0;box-shadow:0 12px 40px #0005}#board-layout-sidebar{width:400px!important}nav{display:none}#demo-label{position:absolute;top:20px;left:40px;font-size:15px;color:#b7cbbd}.square{position:absolute;width:12.5%;height:12.5%;display:flex;align-items:center;justify-content:center;font:54px 'DejaVu Sans';box-sizing:border-box}.sq-white{color:#fff;text-shadow:0 2px 2px #000,1px 0 #333,-1px 0 #333}.sq-black{color:#18231c;text-shadow:0 1px #fff7}''')
 page.evaluate('''()=>{let e=document.createElement('div');e.id='demo-label';e.textContent='MOVE COACH V7 · SIMULASI LOKAL · Auto move → premove';document.body.prepend(e);
 window.drawBoard=fen=>{let b=document.querySelector('wc-chess-board');b.querySelectorAll('.square').forEach(e=>e.remove());
 const map={K:'♔',Q:'♕',R:'♖',B:'♗',N:'♘',P:'♙',k:'♚',q:'♛',r:'♜',b:'♝',n:'♞',p:'♟'};
 let rows=fen.split(' ')[0].split('/');rows.forEach((rank,r)=>{let c=0;for(let v of rank){if(/[1-8]/.test(v)){c+=Number(v);continue;}let e=document.createElement('div');e.className='square '+(v===v.toUpperCase()?'sq-white':'sq-black');e.style.left=c*12.5+'%';e.style.top=r*12.5+'%';e.textContent=map[v];e.dataset.square='abcdefgh'[c]+(8-r);b.append(e);c++;}});
 for(let r=0;r<8;r++)for(let c=0;c<8;c++){let e=document.createElement('div');e.className='square';e.style.left=c*12.5+'%';e.style.top=r*12.5+'%';e.style.background=(r+c)%2?'#64846c':'#d5dfc8';e.style.zIndex='-0';b.prepend(e);}
 };
 drawBoard(fixture.state.fen);
 window.clicks=[];document.querySelector('wc-chess-board').addEventListener('click',e=>{let r=e.currentTarget.getBoundingClientRect();clicks.push('abcdefgh'[Math.floor((e.clientX-r.x)/r.width*8)]+(8-Math.floor((e.clientY-r.y)/r.height*8)));});
 }''')
 presets={str(n):dict(available=True,estimate=n,interval=[n-100,n+100],games=60,target_within_interval=True) for n in range(1500,2301,100)}
 # Use actual calibration evidence, not placeholder ratings.
 from presets import PRESETS
 for n,p in PRESETS.items():presets[str(n)].update(estimate=p.estimate,interval=p.interval,games=p.games,target_within_interval=p.interval[0]<=n<=p.interval[1])
 page.evaluate((ROOT/'panel.js').read_text(),dict(defaults={'elo':1500},presets=presets,configId='v7-video-demo'))
 page.get_by_label('Delay auto move',exact=True).fill('1000');page.get_by_label('Delay auto move',exact=True).dispatch_event('change')
 page.get_by_label('Auto move',exact=True).check()
 auto=AutoMoves();board=chess.Board()
 def run(move,seconds,apply=True):
  done=False;until=time.monotonic()+seconds
  while time.monotonic()<until:
   s=page.evaluate('()=>__chessArrowCoach.poll()')
   payload={'fen':s['fen'],'move':move,'elo':1500,'san':chess.Board(s['fen']).san(chess.Move.from_uci(move)) if chess.Move.from_uci(move) in chess.Board(s['fen']).legal_moves else move,'token':s['token'],'latency_ms':27,'cached':False}
   if s['eligible'] and not done:page.evaluate((ROOT/'overlay.js').read_text(),payload)
   auto.tick(page,s,payload)
   if not done and page.evaluate('clicks.length')>=2:
    assert page.evaluate('clicks.slice(-2)')==[move[:2],move[2:4]]
    if apply:
     board.push_uci(move);page.evaluate('fen=>{fixture.set({fen});drawBoard(fen)}',board.fen())
    done=True
   page.wait_for_timeout(100)
  return done
 page.wait_for_timeout(600)
 assert run('e2e4',3.1)
 page.get_by_role('button',name='Stop · Esc').click()
 page.get_by_label('Langkah premove',exact=True).fill('g1f3')
 page.get_by_role('button',name='Antrekan premove').click()
 page.screenshot(path=str(OUT/'panel.png'))
 page.wait_for_timeout(1300)
 board.push_uci('e7e5');page.evaluate('fen=>{fixture.set({fen});drawBoard(fen);window.clicks=[]}',board.fen())
 assert run('g1f3',3.1)
 page.keyboard.press('Escape');page.wait_for_timeout(1000)
 video=page.video;ctx.close();video.save_as(str(OUT/'demo.webm'));browser.close()
print('Demo recorded: e2e4 and queued g1f3 executed using AutoMoves mouse input')
