#!/usr/bin/env python3
"""Run independent six-opening holdout games for V7 profiles."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, logging, os
from pathlib import Path
import chess, chess.pgn, chess.engine
from calibrate_v7 import FOLDER, PROFILES, OPTIONS, ROOT, play_game
from engine_runtime import engine_specs

HOLDOUT = [
 ('Two Knights quiet','e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Be7'),
 ('Sicilian Kan','e4 c5 Nf3 e6 d4 cxd4 Nxd4 a6'),
 ('Queens Indian','d4 Nf6 c4 e6 Nf3 b6 g3 Ba6'),
 ('Dutch Leningrad','d4 f5 g3 Nf6 Bg2 g6 Nf3 Bg7'),
 ('English QGD','c4 Nf6 Nc3 e6 Nf3 d5 d4 Be7'),
 ('Sicilian early e5','Nf3 c5 e4 Nc6 d4 cxd4 Nxd4 e5'),
]
OUT = ROOT/'validation-v7'

def run(profile):
    model = PROFILES[profile][1]; spec = engine_specs(str(ROOT/'runtime/stockfish'))[model]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    lc0 = chess.engine.SimpleEngine.popen_uci(spec.command, timeout=20, env=env)
    sf = chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'), timeout=20, env=env)
    lc0.configure(OPTIONS); sf.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
    path=OUT/(profile+'.jsonl'); pgn=OUT/(profile+'.pgn')
    rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
    try:
        for index, opening in enumerate(HOLDOUT):
            for white in (True,False):
                if (index,white) in {(r['opening'],r['white']) for r in rows}: continue
                target=PROFILES[profile][0]
                lower=max(r for r in (1320,1700,2100,2500) if r<=target)
                upper=min(r for r in (1320,1700,2100,2500) if r>target)
                reference=(lower,upper)[index%2]
                row,game=play_game(lc0,sf,profile,index,white,opening,reference,'holdout')
                with pgn.open('a') as f:f.write(game+'\n\n')
                with path.open('a') as f:f.write(json.dumps(row)+'\n')
                rows.append(row)
                print('HOLDOUT',profile,f'{len(rows)}/12',flush=True)
    finally: lc0.quit(); sf.quit()
    return profile

def main():
    logging.getLogger('chess.engine').setLevel(logging.ERROR); OUT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for future in as_completed([ex.submit(run,p) for p in PROFILES]): print('COMPLETE',future.result(),flush=True)
    assert all(len((OUT/(p+'.jsonl')).read_text().splitlines())==12 for p in PROFILES)
    print('V7 HOLDOUT COMPLETE: 108 games',flush=True)

if __name__=='__main__': main()
