#!/usr/bin/env python3
"""Exercise the running daemon against isolated, controlled online-board states.

Run after run.py. Uses a fresh browser context and no live matchmaking.
"""
import json
import time
from presets import PRESETS
from pathlib import Path
import chess
from playwright.sync_api import sync_playwright

HTML = '''<!doctype html><html><head><title>Coach integration checks</title></head>
<body><nav><a class="sidebar-link" href="/member/GuestLocal">GuestLocal</a></nav>
<main style="display:flex;gap:24px;margin:30px">
<wc-chess-board style="display:block;position:relative;width:480px;height:480px;background:#b9cb9a"></wc-chess-board>
<aside id="board-layout-sidebar" style="width:300px"></aside></main>
<script>
const state={fen:'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
 white:'GuestLocal',black:'GuestOther',result:'*',atEnd:true,flipped:false,playingAs:null};
window.fixture={state,set:change=>Object.assign(state,change)};
document.querySelector('wc-chess-board').game={
 getFEN:()=>state.fen,getPlayingAs:()=>state.playingAs,getMode:()=>({name:'playing'}),
 getHeaders:()=>({White:state.white,Black:state.black,Result:state.result}),
 getResult:()=>state.result,isAtEndOfLine:()=>state.atEnd,
 getOptions:()=>({flipped:state.flipped})};
</script></body></html>'''


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        context = browser.new_context(viewport={'width': 1100, 'height': 850})
        try:
            context.route('https://www.chess.com/game/coach-ui-test', lambda route: route.fulfill(content_type='text/html', body=HTML))
            page = context.new_page()
            page.goto('https://www.chess.com/game/coach-ui-test')
            page.locator('#human-engine-panel').wait_for(timeout=20000)
            page.get_by_role('button',name='Elo 1500',exact=True).click()

            def update(**values):
                page.evaluate('v=>window.fixture.set(v)', values)

            def reason(value):
                page.wait_for_function('v=>window.__chessArrowCoach?.read()?.reason===v', arg=value, timeout=5000)

            def arrow():
                page.wait_for_function('''()=>{
                  const s=window.__chessArrowCoach?.read(),a=document.querySelector('#human-engine-arrow');
                  return a&&s?.eligible&&a.dataset.fen===s.fen&&Number(a.dataset.elo)===s.prefs.elo;
                }''', timeout=20000)
                data = page.locator('#human-engine-arrow').evaluate('(e)=>({fen:e.dataset.fen,move:e.dataset.move,elo:Number(e.dataset.elo),x1:Number(e.querySelector("line").getAttribute("x1")),y1:Number(e.querySelector("line").getAttribute("y1"))})')
                assert chess.Move.from_uci(data['move']) in chess.Board(data['fen']).legal_moves
                return data

            def no_arrow():
                page.wait_for_function('!document.querySelector("#human-engine-arrow")', timeout=1000)
                page.wait_for_timeout(650)  # An in-flight engine result must not bring it back.
                assert page.locator('#human-engine-arrow').count() == 0

            first = arrow()
            assert page.evaluate('window.__chessArrowCoach.read().playerColor') == 'white'
            print('PASS: online Guest matched to White without playingAs', flush=True)

            board = chess.Board()
            board.push_uci(first['move'])
            black_fen = board.fen()
            update(fen=black_fen)
            reason('opponent'); no_arrow()
            update(flipped=True)
            reason('opponent'); no_arrow()
            assert page.evaluate('window.__chessArrowCoach.read().playerColor') == 'white'
            print('PASS: opponent turn withheld, including after board flip', flush=True)

            update(white='GuestOther', black='GuestLocal', flipped=False)
            black = arrow()
            assert page.evaluate('window.__chessArrowCoach.read().playerColor') == 'black'
            update(flipped=True)
            flipped = arrow()
            assert flipped['move'] == black['move'], 'Flipping should preserve the recommendation'
            m = chess.Move.from_uci(flipped['move'])
            assert flipped['x1'] == (7-chess.square_file(m.from_square))*100+50
            assert flipped['y1'] == chess.square_rank(m.from_square)*100+50
            print('PASS: local Black detected independently of orientation', flush=True)

            page.locator('nav a').evaluate('(e)=>e.remove()')
            reason('unknown'); no_arrow()
            page.get_by_label('Warna pemain', exact=True).select_option('black')
            arrow()
            page.get_by_label('Warna pemain', exact=True).select_option('white')
            reason('opponent'); no_arrow()
            page.get_by_label('Warna pemain', exact=True).select_option('both')
            arrow()
            print('PASS: unknown identity withheld; manual side and analysis override work', flush=True)

            page.get_by_label('Panah aktif', exact=True).uncheck()
            reason('disabled'); no_arrow()
            page.get_by_label('Panah aktif', exact=True).check()
            arrow()
            print('PASS: OFF clears immediately and rejects stale results; ON restores', flush=True)

            assert page.locator('.coach-level').count()==9
            assert page.locator('#human-engine-panel input[type=number]').count()==2
            assert page.get_by_label('Delay auto move',exact=True).count()==1
            assert not page.get_by_label('Engine',exact=True).count()
            assert not page.get_by_label('Batas node',exact=True).count()
            page.get_by_role('button',name='Elo 1600',exact=True).click()
            assert arrow()['elo']==1600
            page.get_by_role('button',name='Elo 1500',exact=True).click()
            assert arrow()['elo']==1500
            print('PASS: nine fixed Elo buttons; no custom Elo, engine or node selector',flush=True)

            before = arrow()['move']
            page.get_by_label('Warna panah', exact=True).fill('#c080ff')
            page.get_by_label('Ketebalan panah', exact=True).fill('22')
            page.wait_for_function('''()=>{
              const line=document.querySelector('#human-engine-arrow line');
              return line?.getAttribute('stroke')==='#c080ff'&&line.getAttribute('stroke-width')==='22';
            }''')
            assert arrow()['move'] == before
            print('PASS: appearance updates preserve the selected move', flush=True)

            update(result='1-0',atEnd=True)
            reason('ended'); no_arrow()
            update(atEnd=False)
            arrow()
            assert page.evaluate('window.__chessArrowCoach.read().phase') == 'review'
            update(result='*',atEnd=False)
            page.get_by_label('Warna pemain', exact=True).select_option('auto')
            reason('history'); no_arrow()
            print('PASS: finished games hidden; post-game review supported; live history withheld', flush=True)

            # Same-tab navigation/reload starts a fresh position and retains controls.
            page.reload()
            page.locator('#human-engine-panel').wait_for(timeout=20000)
            restored = arrow()
            assert restored['elo'] == 1500
            assert page.get_by_label('Warna panah',exact=True).input_value() == '#c080ff'
            assert page.get_by_label('Ketebalan panah',exact=True).input_value() == '22'
            assert page.evaluate('window.__chessArrowCoach.read().playerColor') == 'white'
            print('PASS: new board restores preferences and redetects local player', flush=True)

            # A late result from an older configuration must be rejected even if FEN is equal.
            old = page.evaluate('window.__chessArrowCoach.read()')
            page.get_by_label('Panah aktif',exact=True).uncheck()
            stale = {'fen':old['fen'],'move':restored['move'],'elo':1500,'san':'old','token':old['token']}
            assert not page.evaluate((Path(__file__).parent/'overlay.js').read_text(),stale)
            no_arrow()
            print('PASS: render-time guard rejects outdated recommendations', flush=True)

            page.get_by_label('Panah aktif',exact=True).check()
            arrow()
            status_path=Path(__file__).parent/'runtime/v6-status.json'
            expected={elo:(p.engine,p.nodes) for elo,p in PRESETS.items()}
            for elo,(model,nodes) in expected.items():
                old=page.evaluate('window.__chessArrowCoach.read()')
                page.get_by_role('button',name=f'Elo {elo}',exact=True).click()
                current=arrow();assert current['elo']==elo
                snapshot=page.evaluate('window.__chessArrowCoach.read()')
                assert set(snapshot['prefs'])=={'elo','enabled','color','width','side','autoMove','autoPremove','timeManagement','adaptiveDelay','adaptiveStrength','endgamePremove','advancedPremove','panelCollapsed','badgeEnabled','badgeTitle','badgeStyle','premoveLimit','premoveBreadth','premovePolicy','delay','cursorMs'}
                assert page.get_by_role('button',name=f'Elo {elo}',exact=True).get_attribute('aria-pressed')=='true'
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    status=json.loads(status_path.read_text())
                    if status['token']==snapshot['token']:break
                    time.sleep(.02)
                assert status['token']==snapshot['token'] and status['elo']==elo
                assert (status['engine'],status['nodes'])==(model,nodes)
                visible=page.locator('#human-engine-panel').inner_text().lower()
                assert not any(name in visible for name in ['gyal','girl','lc0','stockfish','maia','node','weight'])
                assert page.locator('#human-engine-arrow').get_attribute('data-engine') is None
                if old['token']!=snapshot['token']:
                    stale={'fen':old['fen'],'move':current['move'],'elo':old['prefs']['elo'],'san':'old','token':old['token']}
                    assert not page.evaluate((Path(__file__).parent/'overlay.js').read_text(),stale)
                print(f'PASS: Elo {elo} real backend routing, legal move, selected button, no model names, stale rejection',flush=True)
            page.get_by_role('button',name='Elo 2300',exact=True).click()
            assert arrow()['elo']==2300
            page.reload()
            page.wait_for_function('document.querySelector("#human-engine-arrow")?.dataset.elo==="2300"',timeout=30000)
            assert page.get_by_role('button',name='Elo 2300',exact=True).get_attribute('aria-pressed')=='true'
            print('PASS: fixed preset survives reload',flush=True)
            page.get_by_role('button',name='Elo 2000',exact=True).click()
            assert arrow()['elo']==2000
            assert 'Target tentatif' in page.locator('[data-field="footer"]').inner_text()
            title=page.get_by_role('button',name='Elo 2000',exact=True).get_attribute('title')
            assert '95%' in title and '60 game' in title
            old=page.evaluate('window.__chessArrowCoach.read()')
            page.evaluate("window.__chessArrowCoach.configId='outdated-test'")
            page.wait_for_function('old=>window.__chessArrowCoach?.configId!=="outdated-test" && window.__chessArrowCoach?.read()?.token!==old',arg=old['token'],timeout=10000)
            assert arrow()['elo']==2000
            stale={'fen':old['fen'],'move':arrow()['move'],'elo':2000,'san':'old','token':old['token']}
            assert not page.evaluate((Path(__file__).parent/'overlay.js').read_text(),stale)
            other=context.new_page();other.goto('https://www.chess.com/game/coach-ui-test')
            other.locator('#human-engine-panel').wait_for(timeout=20000)
            page.get_by_role('button',name='Elo 1500',exact=True).click()
            for tab in [page,other]:
                tab.wait_for_function('document.querySelector("#human-engine-arrow")?.dataset.elo==="1500"',timeout=30000)
            print('PASS: evidence display, tentative labels, config epoch reset, and cross-tab synchronization',flush=True)
            other.close();page.bring_to_front()
            update(fen=chess.STARTING_FEN,white='GuestLocal',black='GuestOther',playingAs=1,
                   result='*',atEnd=True,flipped=False)
            page.evaluate("window.autoClicks=[];document.querySelector('wc-chess-board').addEventListener('click',e=>autoClicks.push([e.clientX,e.clientY]))")
            page.get_by_label('Delay auto move',exact=True).fill('100')
            page.get_by_label('Delay auto move',exact=True).dispatch_event('change')
            page.get_by_label('Auto move',exact=True).check()
            page.wait_for_function('window.autoClicks.length===2',timeout=15000)
            page.wait_for_timeout(1200)
            assert page.evaluate('autoClicks.length')==2
            page.keyboard.press('Escape')
            assert not page.evaluate('window.__chessArrowCoach.read().prefs.autoMove')
            print('PASS: daemon executes real-engine recommendation with mouse input once; Escape disarms',flush=True)
            update(fen=chess.STARTING_FEN,white='GuestOther',black='GuestLocal',playingAs=2,
                   result='*',atEnd=True,flipped=False)
            page.evaluate('window.autoClicks=[]')
            page.get_by_label('Delay auto move',exact=True).fill('0')
            page.get_by_label('Delay auto move',exact=True).dispatch_event('change')
            page.get_by_label('Auto premove',exact=True).check()
            page.wait_for_timeout(1000)
            assert not page.evaluate('autoClicks.length'), 'Never click the speculative move during opponent turn'
            board=chess.Board();board.push_uci('e2e4')
            started=time.monotonic();update(fen=board.fen())
            page.wait_for_function('window.autoClicks.length===2',timeout=10000)
            elapsed=time.monotonic()-started
            assert elapsed<1.5, f'Premove input too slow: {elapsed:.3f}s'
            assert chess.Move.from_uci(arrow()['move']) in board.legal_moves
            page.wait_for_timeout(500);assert page.evaluate('autoClicks.length')==2
            page.keyboard.press('Escape')
            assert not page.evaluate('window.__chessArrowCoach.read().prefs.autoPremove')
            print(f'PASS: own-turn fallback when native API absent, no opponent-turn clicks; reply input {elapsed:.3f}s after turn change',flush=True)



        finally:
            context.close()
    print('ALL BROWSER INTEGRATION CHECK GROUPS PASSED', flush=True)


if __name__ == '__main__':
    main()
