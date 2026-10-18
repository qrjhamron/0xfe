"""Real Chromium input checks on an isolated board; no matchmaking."""
import time
from pathlib import Path
import chess
from playwright.sync_api import sync_playwright
from auto_moves import AutoMoves
from check_browser import HTML
ROOT=Path(__file__).resolve().parent
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 c=b.new_context(viewport={'width':1200,'height':1000})
 c.route('https://www.chess.com/game/auto-test',lambda r:r.fulfill(content_type='text/html',body=HTML))
 page=c.new_page();page.goto('https://www.chess.com/game/auto-test')
 opts={'defaults':{'elo':1500},'presets':{str(n):dict(available=True,estimate=n,interval=[n-100,n+100],games=60,target_within_interval=True) for n in range(1500,2301,100)},'configId':'v8-test'}
 page.evaluate((ROOT/'panel.js').read_text(),opts)
 page.evaluate("window.clicks=[];document.querySelector('wc-chess-board').addEventListener('click',e=>clicks.push([e.clientX,e.clientY]))")
 auto=AutoMoves()
 def read():return page.evaluate('()=>__chessArrowCoach.poll()')
 def drive(move='e2e4',seconds=.7):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   s=read();auto.tick(page,s,{'move':move,'token':s['token']});page.wait_for_timeout(15)
 assert not read()['prefs']['autoMove'] and not read()['prefs']['autoPremove']
 assert not page.get_by_label('Langkah premove',exact=True).count()
 page.get_by_label('Delay auto move',exact=True).fill('0');page.get_by_label('Delay auto move',exact=True).dispatch_event('change')
 page.get_by_label('Durasi kursor',exact=True).fill('120');page.get_by_label('Durasi kursor',exact=True).dispatch_event('change')
 page.get_by_label('Auto premove',exact=True).check()
 start=time.monotonic();drive(seconds=.5);elapsed=time.monotonic()-start
 assert page.evaluate('clicks.length')==2
 assert elapsed<.8
 drive(seconds=.2);assert page.evaluate('clicks.length')==2
 print('PASS: auto premove needs no coordinates; cursor/input finishes in under 0.8s without duplicate clicks')
 page.keyboard.press('Escape');assert not read()['prefs']['autoPremove']
 page.evaluate('clicks=[]');page.get_by_label('Auto move',exact=True).check()
 s=read();auto.tick(page,s,{'move':'d2d4','token':'STALE'});assert auto.job is None
 auto.tick(page,s,{'move':'d2d4','token':s['token']});page.keyboard.press('Escape');drive(seconds=.2)
 assert not page.evaluate('clicks.length') and auto.job is None
 print('PASS: Escape disarms both toggles; stale recommendations never click')
 # Full automatic underpromotion, using the site's supported promotion selector classes.
 fen='7k/P7/8/8/8/8/8/7K w - - 0 1'
 page.evaluate('fen=>fixture.set({fen,playingAs:1})',fen)
 page.evaluate("()=>{let e=document.createElement('button');e.className='promotion-piece wn';e.textContent='Knight';e.style.cssText='position:fixed;left:600px;top:700px';e.onclick=()=>window.promoted=true;document.body.append(e)}")
 page.get_by_label('Auto move',exact=True).check();drive('a7a8n',seconds=.6)
 assert page.evaluate('window.promoted===true')
 print('PASS: promotion automatically selects the recommended piece, including knight underpromotion')
 page.evaluate('__chessArrowCoach.destroy()');page.evaluate((ROOT/'panel.js').read_text(),opts)
 assert not read()['prefs']['autoMove'] and not read()['prefs']['autoPremove']
 print('PASS: reload always disarms automation')
 # Settings can scroll a short browser window so the board is above the viewport.
 page.evaluate("fixture.set({fen:'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',playingAs:1});clicks=[];document.body.style.minHeight='3000px'")
 page.get_by_label('Auto move',exact=True).check()
 page.evaluate('scrollTo(0,1000)')
 assert page.evaluate("document.querySelector('wc-chess-board').getBoundingClientRect().bottom<0")
 auto=AutoMoves();drive(seconds=.7)
 assert page.evaluate('clicks.length')==2
 assert page.evaluate("document.querySelector('wc-chess-board').getBoundingClientRect().top>=0")
 print('PASS: an offscreen board is brought into view before real mouse input')
 b.close()
print('ALL AUTOMATION CHECKS PASSED')
