#!/usr/bin/env python3
"""Fresh, audited fixed-level calibration; no Chess.com/FIDE rating claim."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
import hashlib
import json
import logging
from pathlib import Path
import time
import chess
import chess.engine
import chess.pgn
from engine_runtime import engine_specs
from rate_weights import OPENINGS,opening_board

ROOT=Path(__file__).resolve().parent
REFERENCES=[1320,1700,2100,2500]
# Profile IDs are for audit only. User-facing reports need no model identities.
PROFILES={
 'p1500a':(1500,'meangirl7',1),
 'p1500b':(1500,'meangirl7',2),
 'p1600':(1600,'meangirl7',4),
 'p1700':(1700,'evilgyal6',8),
 'p1800':(1800,'goodgyal5',8),
 'p1900':(1900,'goodgyal5',12),
 'p2000':(2000,'badgyal8',4),
 'p2100':(2100,'badgyal8',8),
 'p2200':(2200,'badgyal8',12),
 'p2300':(2300,'badgyal8',24),
 'p2100r':(2100,'badgyal8',6),
 'p2300r':(2300,'badgyal8',10),
 'p2100s':(2100,'badgyal8',5),
}
OPTIONS={'Threads':1,'MinibatchSize':1,'NNCacheSize':20000,
         'SmartPruningFactor':'0','RamLimitMb':128,'MaxPrefetch':0}


def play_game(lc0,sf,profile,index,white,opening_override=None,reference_override=None):
    target,model,nodes=PROFILES[profile]
    if opening_override is None:
        board=opening_board(index);opening_name=OPENINGS[index][0]
    else:
        board=chess.Board();opening_name=opening_override[0]
        for san in opening_override[1].split():board.push_san(san)
    opening_plies=board.ply()
    reference=REFERENCES[index%4] if reference_override is None else reference_override
    sf.configure({'UCI_Elo':reference})
    identity=f'{profile}-{index}-{int(white)}';started=time.monotonic()
    measurements=[];termination=None
    while not board.is_game_over(claim_draw=True):
        if board.ply()>=300:
            termination='ply-cap';break
        ours=board.turn==white;engine=lc0 if ours else sf
        limit=chess.engine.Limit(nodes=nodes,time=2) if ours else chess.engine.Limit(time=.05)
        t=time.monotonic()
        result=engine.play(board,limit,game=identity,info=chess.engine.INFO_BASIC if ours else chess.engine.INFO_NONE)
        if result.move not in board.legal_moves:raise RuntimeError('Illegal move: '+identity)
        if ours:measurements.append({'nodes':result.info.get('nodes'),'ms':round((time.monotonic()-t)*1000,2)})
        board.push(result.move)
    outcome=board.outcome(claim_draw=True)
    if outcome:
        result_string=outcome.result();termination=outcome.termination.name.lower()
        score=.5 if outcome.winner is None else int(outcome.winner==white)
    else:result_string='1/2-1/2';score=.5
    game=chess.pgn.Game.from_board(board)
    game.headers.update({'Event':'V6 local level calibration','Site':'Local CPU',
       'Date':datetime.now(timezone.utc).strftime('%Y.%m.%d'),'Round':str(index+1),
       'White':profile if white else f'Stockfish UCI_Elo {reference}',
       'Black':f'Stockfish UCI_Elo {reference}' if white else profile,
       'Result':result_string,'Opening':opening_name,'Termination':termination,
       'Profile':profile,'NodeBudget':str(nodes),'ReferenceElo':str(reference),
       'StockfishMoveTime':'0.05','MaxPrefetch':'0'})
    if termination=='ply-cap':game.end().comment='Administrative draw at 300 ply; not a rule-based draw.'
    row={'profile':profile,'target':target,'nodes':nodes,'opening':index,'opening_plies':opening_plies,
         'white':white,'reference_elo':reference,'score':score,'result':result_string,
         'termination':termination,'plies':board.ply(),'seconds':round(time.monotonic()-started,2),
         'searches':measurements}
    return row,str(game)


def run_profile(profile,folder):
    _,model,_=PROFILES[profile];spec=engine_specs(str(ROOT/'runtime/stockfish'))[model]
    environment=__import__('os').environ.copy();environment.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    lc0=chess.engine.SimpleEngine.popen_uci(spec.command,timeout=20,env=environment)
    sf=chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'),timeout=20,env=environment)
    lc0.configure(OPTIONS);sf.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
    path=folder/(profile+'.jsonl');pgn=folder/(profile+'.pgn')
    rows=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    done={(r['opening'],r['white']) for r in rows}
    try:
        for index in range(24):
            for white in [True,False]:
                if (index,white) in done:continue
                row,game=play_game(lc0,sf,profile,index,white)
                with pgn.open('a') as f:f.write(game+'\n\n')
                with path.open('a') as f:f.write(json.dumps(row)+'\n')
                rows.append(row)
                w=sum(r['score']==1 for r in rows);d=sum(r['score']==.5 for r in rows)
                print(f'{profile} {len(rows)}/48 W{w} D{d} L{len(rows)-w-d}; '
                      f'vs {row["reference_elo"]} {row["result"]} {row["termination"]} {row["seconds"]}s',flush=True)
    finally:lc0.quit();sf.quit()
    return profile



def finish_last_parallel(folder,profile='p2300'):
    """Resume remaining last-profile games with two independent engine pairs."""
    import queue
    import threading
    import os
    path=folder/(profile+'.jsonl');pgn=folder/(profile+'.pgn')
    rows=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    done={(r['opening'],r['white']) for r in rows};jobs=queue.Queue();lock=threading.Lock()
    for index in range(24):
        for white in [True,False]:
            if (index,white) not in done:jobs.put((index,white))
    def worker():
        spec=engine_specs(str(ROOT/'runtime/stockfish'))[PROFILES[profile][1]]
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        lc0=chess.engine.SimpleEngine.popen_uci(spec.command,timeout=20,env=env)
        sf=chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'),timeout=20,env=env)
        lc0.configure(OPTIONS);sf.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
        try:
            while True:
                try:index,white=jobs.get_nowait()
                except queue.Empty:return
                row,game=play_game(lc0,sf,profile,index,white)
                with lock:
                    with pgn.open('a') as f:f.write(game+'\n\n')
                    with path.open('a') as f:f.write(json.dumps(row)+'\n')
                    rows.append(row)
                    w=sum(r['score']==1 for r in rows);d=sum(r['score']==.5 for r in rows)
                    print(f'{profile} {len(rows)}/48 W{w} D{d} L{len(rows)-w-d}; parallel resume',flush=True)
        finally:lc0.quit();sf.quit()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(worker) for _ in range(2)]
        for future in futures:future.result()
    assert len(rows)==48


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'calibration-v6')
    args=parser.parse_args();folder=args.output;folder.mkdir(exist_ok=True)
    logging.getLogger('chess.engine').setLevel(logging.ERROR)
    config={'profiles':PROFILES,'references':REFERENCES,'engine_options':OPTIONS,
      'lc0_seconds_ceiling':2,'stockfish_seconds':.05,'stockfish_options':{'Threads':1,'Hash':16,'UCI_LimitStrength':True},
      'games_per_profile':48,'opening_pairs':24,'max_plies':300,'workers':2,
      'draw_protocol':'Claimable threefold/50-move draws; no evaluation adjudication; capped games separately reported',
      'created_utc':datetime.now(timezone.utc).isoformat(),
      'limitation':'Local Stockfish UCI_Elo-reference only; bootstrap excludes systematic calibration and clock bias',
      'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
          [ROOT/'runtime/lc0',ROOT/'runtime/stockfish',*sorted((ROOT/'runtime/lc0-weights').glob('*.pb.gz'))]}}
    config=json.loads(json.dumps(config));file=folder/'config.json'
    if file.exists():
        old=json.loads(file.read_text())
        assert all(old[k]==v for k,v in config.items() if k!='created_utc'),'Resume config mismatch'
    else:file.write_text(json.dumps(config,indent=2))
    def complete(key):
        path=folder/(key+'.jsonl')
        return path.exists() and len(path.read_text().splitlines())==48
    if all(complete(key) for key in PROFILES if key!='p2300'):
        if not complete('p2300'):finish_last_parallel(folder)
        print('V6 CALIBRATION COMPLETE',flush=True)
        return
    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks=[executor.submit(run_profile,key,folder) for key in PROFILES]
        for task in as_completed(tasks):print('COMPLETE',task.result(),flush=True)
    print('V6 CALIBRATION COMPLETE',flush=True)

if __name__=='__main__':main()
