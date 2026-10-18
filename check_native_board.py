"""Optional check on a PREPARED LOCAL site board; never run against a live game.

The page must be /play/online?coach-native-test=1 with playing mode and the
site's native premoves API already available. This script installs no plugin
and does not enter matchmaking. This proves local site behavior, not online play.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import chess
from playwright.sync_api import sync_playwright
from presets import PRESETS

ROOT=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cdp',default='http://127.0.0.1:9224')
    args=ap.parse_args()
    with sync_playwright() as p:
        b=p.chromium.connect_over_cdp(args.cdp)
        pages=[q for c in b.contexts for q in c.pages
               if urlsplit(q.url).path=='/play/online' and parse_qs(urlsplit(q.url).query).get('coach-native-test')==['1']]
        if len(pages)!=1:raise SystemExit('Prepare exactly one local /play/online?coach-native-test=1 page first; no live game is modified.')
        q=pages[0];q.bring_to_front()
        if not q.evaluate('!!document.querySelector("wc-chess-board")?.game?.premoves?.move'):
            raise SystemExit('Prepared local board must provide the actual native premoves API.')
        q.evaluate('''()=>{const g=document.querySelector('wc-chess-board').game;g.premoves.cancel();g.resetGame();g.setPlayingAs(2)}''')
        presets={str(n):dict(available=True,estimate=v.estimate,interval=v.interval,games=v.games,target_within_interval=v.interval[0]<=n<=v.interval[1]) for n,v in PRESETS.items()}
        q.evaluate((ROOT/'panel.js').read_text(),{'defaults':{'elo':1500},'presets':presets,'configId':'v10-local-native'})
        q.get_by_label('Auto premove',exact=True).check()
        board=chess.Board()
        pairs=[('e2e4','e7e5'),('g1f3','b8c6'),('f1b5','a7a6'),('b5a4','g8f6'),('e1g1','f8e7'),('f1e1','b7b5')]
        for index,(opp,own) in enumerate(pairs):
            s=q.evaluate('()=>__chessArrowCoach.poll()')
            base=board.fen(en_passant='fen');board.push_uci(opp);before=board.fen(en_passant='fen');board.push_uci(own);after=board.fen(en_passant='fen')
            payload={'base':base,'token':s['token'],'plan':[{'move':own,'before':before,'after':after}]}
            assert q.evaluate('p=>__chessArrowCoach.queueNative(p)',payload)
            assert q.evaluate('()=>__chessArrowCoach.read().native.queue')==[own]
            assert q.evaluate('()=>__chessArrowCoach.read().fen')==base
            # Only the opponent is advanced by the local harness. The site consumes our queue.
            q.evaluate("m=>document.querySelector('wc-chess-board').game.move({from:m.slice(0,2),to:m.slice(2,4),userGenerated:false})",opp)
            s=q.evaluate('()=>__chessArrowCoach.read()')
            a=q.evaluate('()=>__chessArrowCoach.audit()')
            assert s['fen']==after and s['native']['queue']==[],(s,a)
            assert a['counts']['queued']==index+1 and a['counts']['used']==index+1,a
        q.screenshot(path=str(ROOT/'runtime/v10-native-real.png'))
        audit=q.evaluate('()=>__chessArrowCoach.audit()')
        (ROOT/'runtime/v10-native-real.json').write_text(json.dumps({'scope':'local-site-board','online_match':False,**audit},indent=2))
        q.keyboard.press('Escape')
        print('PASS: actual site board consumed six successive single premoves; confirmed native events; no own-turn move calls')
        print('ALL LOCAL SITE NATIVE CHECKS PASSED (NOT MATCHMAKING)')


if __name__=='__main__':main()
