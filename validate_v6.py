#!/usr/bin/env python3
"""Independent opening set for checking selected fixed-level candidates."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
import logging
import os
from pathlib import Path
import chess
import chess.engine
from calibrate_v6 import ROOT,OPTIONS,PROFILES,REFERENCES,play_game
from engine_runtime import engine_specs
HOLDOUT=[
 ('Two Knights quiet','e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Be7'),
 ('Sicilian Kan','e4 c5 Nf3 e6 d4 cxd4 Nxd4 a6'),
 ('Queens Indian','d4 Nf6 c4 e6 Nf3 b6 g3 Ba6'),
 ('Dutch Leningrad','d4 f5 g3 Nf6 Bg2 g6 Nf3 Bg7'),
 ('English QGD','c4 Nf6 Nc3 e6 Nf3 d5 d4 Be7'),
 ('Sicilian early e5','Nf3 c5 e4 Nc6 d4 cxd4 Nxd4 e5'),
]
HOLDOUT_2100=[
 ('Berlin quiet','e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Be7'),
 ('Sicilian Taimanov','e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6'),
 ('Caro exchange','e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6'),
 ('Modern Benoni','d4 Nf6 c4 c5 d5 e6 Nc3 exd5 cxd5 d6'),
 ('Queens gambit accepted','d4 d5 c4 dxc4 Nf3 Nf6 e3 e6'),
 ('Reti advance','Nf3 d5 c4 d4 e3 Nc6 exd4 Nxd4'),
]
FOLDER=ROOT/'validation-v6'


def run(target,preset):
    profile=preset['profile'];model=preset['engine']
    assert tuple(PROFILES[profile][1:])==(model,preset['nodes'])
    command=engine_specs(str(ROOT/'runtime/stockfish'))[model].command
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    lc0=chess.engine.SimpleEngine.popen_uci(command,timeout=20,env=env)
    sf=chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'),timeout=20,env=env)
    lc0.configure(OPTIONS);sf.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
    target=int(target);lower=max(r for r in REFERENCES if r<=target);upper=min(r for r in REFERENCES if r>target)
    path=FOLDER/(str(target)+'.jsonl');pgn=FOLDER/(str(target)+'.pgn')
    rows=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    done={(r['opening'],r['white']) for r in rows}
    try:
        cases=HOLDOUT_2100 if profile=='p2100s' else HOLDOUT
        for index,opening in enumerate(cases):
            for white in [True,False]:
                if (index,white) in done:continue
                reference=[lower,upper][index%2]
                row,game=play_game(lc0,sf,profile,index,white,opening,reference)
                row['target']=target;row['dataset']='holdout'
                with pgn.open('a') as f:f.write(game+'\n\n')
                with path.open('a') as f:f.write(json.dumps(row)+'\n')
                rows.append(row)
                print('HOLDOUT',target,f'{len(rows)}/12','points',sum(r['score'] for r in rows),flush=True)
    finally:lc0.quit();sf.quit()
    return target


def main():
    logging.getLogger('chess.engine').setLevel(logging.ERROR)
    for _,line in HOLDOUT+HOLDOUT_2100:
        board=chess.Board()
        for san in line.split():board.push_san(san)
    selected=json.loads((ROOT/'calibration-profiles.json').read_text())['presets']
    FOLDER.mkdir(exist_ok=True)
    config={'created_utc':datetime.now(timezone.utc).isoformat(),'selected':selected,'openings':HOLDOUT,'replacement_2100_openings':HOLDOUT_2100,
        'games_per_preset':12,'engine_options':OPTIONS,'stockfish_seconds':.05,
        'selection_policy':'No changes to selected node budgets based on the holdout results.'}
    file=FOLDER/'config.json'
    if file.exists():
        old=json.loads(file.read_text())['selected']
        signature=lambda values:{target:(p['profile'],p['engine'],p['nodes']) for target,p in values.items()}
        if signature(old)!=signature(selected):
            for target,identity in signature(selected).items():
                path=FOLDER/(target+'.jsonl')
                if signature(old).get(target)!=identity:
                    assert not path.exists() or not path.read_text().strip(),'Cannot change a profile whose holdout started: '+target
            previous=json.loads(file.read_text())
            previous['previous_selection']=old;previous['selected']=selected
            previous['revision_reason']='High-level profiles refined from calibration before their holdout games. Lower-level results retained unchanged.'
            file.write_text(json.dumps(previous,indent=2)+'\n')
    else:file.write_text(json.dumps(config,indent=2))
    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks=[executor.submit(run,target,preset) for target,preset in selected.items()]
        for task in as_completed(tasks):print('HOLDOUT COMPLETE',task.result(),flush=True)
    print('108 HOLDOUT GAMES COMPLETE',flush=True)

if __name__=='__main__':main()
