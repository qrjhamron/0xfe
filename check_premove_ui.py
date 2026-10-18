"""Isolated native-contract checks. No online matchmaking or server claims."""
from pathlib import Path
import json
import tempfile
import chess
from playwright.sync_api import sync_playwright
from check_browser import HTML
from session_audit import SessionAudit

ROOT=Path(__file__).resolve().parent
NATIVE=r'''()=>{
 const g=document.querySelector('wc-chess-board').game;
 let queue=[],handlers=[];
 const api={move:m=>queue.push({...m}),getQueue:()=>queue,cancel:()=>{queue=[]}};
 g.premoves=api;g.onAll=f=>handlers.push(f);g.offAll=f=>{handlers=handlers.filter(x=>x!==f)};
 fixture.nativeApi=api;
 fixture.emit=e=>handlers.forEach(f=>f(e));
 fixture.consume=p=>{
   if(!queue.length)throw Error('No native queue');
   const m=queue.shift();fixture.state.fen=p.after;
   if(p.event!==false)fixture.emit({consumedPremove:true,move:m});
 };
 fixture.handlerCount=()=>handlers.length;
}'''


def main():
    with sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        c=b.new_context(viewport={'width':1440,'height':1000})
        c.route('https://www.chess.com/game/native-contract',lambda r:r.fulfill(content_type='text/html',body=HTML))
        q=c.new_page();q.goto('https://www.chess.com/game/native-contract')
        q.evaluate('fixture.set({playingAs:2})');q.evaluate(NATIVE)
        presets={str(n):dict(available=True,estimate=n,interval=[n-100,n+100],games=60,target_within_interval=True) for n in range(1500,2301,100)}
        opts={'defaults':{'elo':1500},'presets':presets,
              'engines':{'maia3':{'label':'Maia 3 · gaya manusia','available':True}},
              'configId':'v10-native-contract'}
        q.evaluate((ROOT/'panel.js').read_text(),opts)
        assert q.get_by_label('Tutup panel',exact=True).count()==1
        assert q.locator('[data-move-coach-game-title]').count()==2
        assert q.locator('[data-move-coach-game-title]').all_inner_texts()==['GM','GM']
        q.get_by_label('Tutup panel',exact=True).click()
        assert q.locator('.coach-body').is_hidden()
        assert q.get_by_label('Buka panel',exact=True).count()==1
        q.get_by_label('Buka panel',exact=True).click()
        assert q.locator('.coach-body').is_visible()
        delay=q.get_by_label('Delay auto move',exact=True)
        assert delay.is_disabled()
        q.get_by_label('Adaptive auto move delay',exact=True).uncheck()
        assert not delay.is_disabled()
        q.get_by_label('Adaptive auto move delay',exact=True).check()
        assert delay.is_disabled()
        q.get_by_label('Mode mesin',exact=True).select_option('maia3')
        assert q.evaluate('()=>__chessArrowCoach.poll().prefs.engine')=='maia3'
        q.get_by_label('Mode mesin',exact=True).select_option('calibrated')
        q.get_by_label('Gelar visual',exact=True).select_option('IM')
        assert q.locator('[data-move-coach-game-title]').all_inner_texts()==['IM','IM']
        q.get_by_label('Profil visual',exact=True).uncheck()
        assert q.locator('[data-move-coach-game-title]').count()==0
        q.get_by_label('Profil visual',exact=True).check()
        assert q.locator('[data-move-coach-game-title]').count()==2
        print('PASS: adaptive delay locks the manual delay field and restores it when disabled')
        print('PASS: panel opens/closes from the header without removing the arrow coach state')
        q.get_by_label('Auto premove',exact=True).check()
        q.get_by_label('Cabang premove',exact=True).select_option('8')
        def read():return q.evaluate('()=>__chessArrowCoach.poll()')
        def audit():return q.evaluate('()=>__chessArrowCoach.audit()')
        board=chess.Board()
        pairs=[('e2e4','e7e5'),('g1f3','b8c6'),('f1b5','a7a6'),('b5a4','g8f6'),('e1g1','f8e7'),('f1e1','b7b5')]
        for index,(op,own) in enumerate(pairs):
            s=read();assert s['reason']=='opponent'
            base=board.fen(en_passant='fen');board.push_uci(op);before=board.fen(en_passant='fen');board.push_uci(own);after=board.fen(en_passant='fen')
            item={'move':own,'before':before,'after':after,'states':[before,after]}
            payload={'base':base,'token':s['token'],'plan':[item]}
            assert not q.evaluate('p=>__chessArrowCoach.queueNative({...p,plan:[...p.plan,...p.plan]})',payload)
            assert q.evaluate('p=>__chessArrowCoach.queueNative(p)',payload)
            assert q.evaluate('p=>__chessArrowCoach.queueNative(p)',payload)
            assert read()['native']['queue']==[own] and read()['fen']==base
            assert audit()['counts']['queued']==index+1
            q.evaluate("m=>fixture.emit({consumedPremove:()=>true,move:{from:m.slice(0,2),to:m.slice(2,4)}})",own)
            assert audit()['counts']['used']==index
            q.evaluate('p=>fixture.consume(p)',{'after':after})
            assert read()['native']['queue']==[] and audit()['counts']['used']==index+1
            q.evaluate("m=>fixture.emit({consumedPremove:true,move:{from:m.slice(0,2),to:m.slice(2,4)}})",own)
            assert audit()['counts']['used']==index+1
        assert audit()['counts']['queued']==6 and audit()['counts']['used']==6
        assert len({e['gameId'] for e in audit()['events']})==1
        first_snapshot,first_audit=read(),audit()
        print('PASS: six consecutive native-contract queue/consume/refill cycles; one item each; duplicates and truthy functions excluded')
        s=read();q.evaluate('delete document.querySelector("wc-chess-board").game.premoves')
        assert not read()['native']['supported']
        q.evaluate("localStorage.setItem('settingsHttpCache',JSON.stringify({u:{keys:{settings:{'gameplay.live.premoves':false}}}}))")
        read();assert 'nonaktif' in q.locator('[data-field=native-status]').inner_text()
        assert q.locator('[data-action=site-premove]').is_visible()
        q.evaluate('document.querySelector("wc-chess-board").game.premoves=fixture.nativeApi')
        assert read()['native']['supported'] and audit()['counts']['used']==6
        print('PASS: missing native API and disabled site preference are explicit; API recovery preserves audit')
        s=read();report={'token':s['token'],'base':s['fen'],'branches':[{'opponent':'h2h3','reply':'a7a5'}],
                         'message':'Reading branches','coverage':{'compatible':2,'total':3}}
        assert q.evaluate('p=>__chessArrowCoach.premoveState(p)',report)
        q.locator('details summary').click()
        assert 'h2h3' in q.locator('[data-field=premove-plan]').inner_text()
        assert not q.evaluate('p=>__chessArrowCoach.premoveState({...p,token:"STALE"})',report)
        q.evaluate('history.pushState({},"","/game/another-game");fixture.set({fen:"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"})')
        s=read();assert audit()['counts']['queued']==0 and audit()['counts']['used']==0
        with tempfile.TemporaryDirectory() as folder:
            writer=SessionAudit(folder)
            writer.sync(first_snapshot,first_audit,'https://www.chess.com/game/first')
            current=audit();current['events']=first_audit['events']
            writer.sync(s,current,'https://www.chess.com/game/second')
            writer.sync(s,first_audit,'https://www.chess.com/game/second')
            saved=[json.loads(path.read_text()) for path in Path(folder).glob('*.json')]
            assert len(saved)==2
            assert sorted(x['counts']['used'] for x in saved)==[0,6]
            assert all(all(e['gameId']==x['game_id'] for e in x['events']) for x in saved)
        print('PASS: persistent audit isolates game files and rejects late events from another game')
        board=chess.Board();board.push_uci('e2e4');before=board.fen(en_passant='fen');board.push_uci('e7e5');after=board.fen(en_passant='fen')
        payload={'base':s['fen'],'token':s['token'],'plan':[{'move':'e7e5','before':before,'after':after}]}
        assert q.evaluate('p=>__chessArrowCoach.queueNative(p)',payload)
        q.evaluate('p=>fixture.consume(p)',{'after':after,'event':False})
        read();assert audit()['counts']['observed']==1 and audit()['counts']['used']==0
        print('PASS: new game resets counters; FEN-only observations stay separate from confirmed native events')
        q.keyboard.press('Escape');assert not read()['prefs']['autoPremove']
        q.evaluate('__chessArrowCoach.destroy()');q.evaluate((ROOT/'panel.js').read_text(),opts)
        assert not read()['prefs']['autoPremove'] and q.evaluate('fixture.handlerCount()')==1
        b.close()
        print('PASS: reload disarms and detaches the previous listener')
    print('ALL NATIVE CONTRACT CHECKS PASSED')


if __name__=='__main__':main()
