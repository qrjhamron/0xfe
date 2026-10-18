#!/usr/bin/env python3
"""Small candidate sweep for the requested 1550–1750 low-level bands."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, logging, os, time
from pathlib import Path
import chess, chess.engine
from engine_runtime import engine_specs
import calibrate_v7_targeted as base
from rate_weights import OPENINGS, opening_board
from summarize_ratings import summarize

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'candidate-sweep-low'
CANDIDATES={
    'm6':(1600,'meangirl7',6),
    'e4':(1700,'evilgyal6',4),
    'e6':(1700,'evilgyal6',6),
    'g6':(1700,'goodgyal5',6),
    'g7':(1700,'goodgyal5',7),
}
OPTIONS=base.OPTIONS

def run(name):
    target,model,nodes=CANDIDATES[name]
    spec=engine_specs(str(ROOT/'runtime/stockfish'))[model]
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    lc0=chess.engine.SimpleEngine.popen_uci(spec.command,timeout=20,env=env)
    sf=chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'),timeout=20,env=env)
    lc0.configure(OPTIONS);sf.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
    path=OUT/(name+'.jsonl');rows=[]
    try:
        for index in range(12):
            for white in (True,False):
                board=opening_board(index);ref=(1320,1700,2100,2500)[index%4]
                sf.configure({'UCI_Elo':ref})
                started=time.monotonic(); identity=f'sweep-{name}-{index}-{int(white)}'
                measurements=[]
                while not board.is_game_over(claim_draw=True):
                    if board.ply()>=300: break
                    ours=board.turn==white; engine=lc0 if ours else sf
                    result=engine.play(board,chess.engine.Limit(nodes=nodes,time=2) if ours else chess.engine.Limit(time=.05),game=identity,info=chess.engine.INFO_BASIC if ours else chess.engine.INFO_NONE)
                    if ours: measurements.append({'nodes':result.info.get('nodes'),'ms':0})
                    board.push(result.move)
                outcome=board.outcome(claim_draw=True)
                score=.5 if not outcome or outcome.winner is None else int(outcome.winner==white)
                rows.append({'profile':name,'target':target,'nodes':nodes,'opening':index,'white':white,
                    'reference_elo':ref,'score':score,'result':outcome.result() if outcome else '1/2-1/2',
                    'termination':outcome.termination.name.lower() if outcome else 'ply-cap','plies':board.ply(),
                    'seconds':round(time.monotonic()-started,2),'searches':measurements})
                print(name,len(rows),rows[-1]['result'],flush=True)
    finally: lc0.quit();sf.quit()
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    return name,summarize(rows)

def main():
    logging.getLogger('chess.engine').setLevel(logging.ERROR);OUT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures=[ex.submit(run,n) for n in CANDIDATES]
        for f in as_completed(futures):
            name,result=f.result();print('RESULT',name,result['local_reference_performance'],result['bootstrap_95_interval'],f"{result['wins']}-{result['draws']}-{result['losses']}",flush=True)

if __name__=='__main__':main()
