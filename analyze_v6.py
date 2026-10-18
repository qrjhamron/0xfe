#!/usr/bin/env python3
"""Audit fresh calibration games and produce provisional fixed-level mappings."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
import chess
import chess.pgn
from calibrate_v6 import PROFILES,REFERENCES,OPENINGS,opening_board,run_profile,finish_last_parallel
from concurrent.futures import ThreadPoolExecutor
from summarize_ratings import summarize
ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'calibration-v6'


def audit(profile,rows):
    assert len(rows)==48
    assert {(r['opening'],r['white']) for r in rows}=={(i,c) for i in range(24) for c in [True,False]}
    nodes=PROFILES[profile][2]
    with (FOLDER/(profile+'.pgn')).open() as f:
        for row in rows:
            game=chess.pgn.read_game(f);assert game and not game.errors
            assert game.headers['Profile']==profile and int(game.headers['NodeBudget'])==nodes
            assert int(game.headers['MaxPrefetch'])==0
            assert row['nodes']==nodes and row['profile']==profile
            assert row['reference_elo']==REFERENCES[row['opening']%4]
            assert game.headers['Result']==row['result']
            assert (game.headers['White']==profile)==row['white']
            board=game.board()
            for move in game.mainline_moves():
                assert move in board.legal_moves;board.push(move)
                if board.ply()==row['opening_plies']:assert board.fen()==opening_board(row['opening']).fen()
            assert board.ply()==row['plies']
            outcome=board.outcome(claim_draw=True)
            if row['termination']!='ply-cap':
                assert outcome and outcome.result()==row['result']
                assert outcome.termination.name.lower()==row['termination']
                assert row['score']==(.5 if outcome.winner is None else int(outcome.winner==row['white']))
        assert chess.pgn.read_game(f) is None


def main():
    config=json.loads((FOLDER/'config.json').read_text())
    config.setdefault('initial_profiles',config['profiles'])
    config['profiles']=PROFILES
    config['calibration_games']=624
    plan={'reason':'Initial candidate at 12 nodes measured 2390 while 8 nodes measured 2208. Refine the gap instead of forcing labels.',
          'basis':'Calibration results only; no validation outcome is used to select budgets.',
          'extra_candidates':{k:PROFILES[k] for k in ['p2100r','p2300r']},
          'additional_games':96,'label_mapping':'2100 uses refined 6-node candidate; 2200 uses measured 8-node candidate; 2300 uses refined 10-node candidate'}
    config['refinement']=plan
    (FOLDER/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (FOLDER/'refinement-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    todo=[]
    for key in ['p2100r','p2300r']:
        path=FOLDER/(key+'.jsonl')
        if not path.exists() or len(path.read_text().splitlines())!=48:todo.append(key)
    if todo:
        with ThreadPoolExecutor(max_workers=2) as executor:
            for future in [executor.submit(run_profile,key,FOLDER) for key in todo]:future.result()
    extra=FOLDER/'p2100s.jsonl'
    if not extra.exists() or len(extra.read_text().splitlines())!=48:
        finish_last_parallel(FOLDER,'p2100s')
    final_plan=FOLDER/'final-refinement-plan.json'
    config['final_refinement']=(json.loads(final_plan.read_text()) if final_plan.exists() else
        {'reason':'Repeat the published 5-node refinement without further adaptation','calibration_games':48})
    (FOLDER/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    results={}
    for profile in PROFILES:
        rows=[json.loads(x) for x in (FOLDER/(profile+'.jsonl')).read_text().splitlines()]
        audit(profile,rows);result=summarize(rows)
        searches=[s for r in rows for s in r['searches']]
        times=sorted(s['ms'] for s in searches)
        known=[s['nodes'] for s in searches if s['nodes'] is not None]
        result['search_stats']={'moves':len(searches),'unknown_node_counts':len(searches)-len(known),
             'node_shortfalls':sum(n<PROFILES[profile][2] for n in known),
             'p50_ms':round(statistics.median(times),2),'p95_ms':times[int((len(times)-1)*.95)],
             'max_ms':max(times),'min_reported_nodes':min(known) if known else None,
             'max_reported_nodes':max(known) if known else None}
        result['node_budget']=PROFILES[profile][2]
        assert result['search_stats']['unknown_node_counts']==0
        assert result['search_stats']['node_shortfalls']<.05*len(searches),'Too many time-capped searches: '+profile
        results[profile]=result
        print('AUDITED',profile,result['local_reference_performance'],result['bootstrap_95_interval'],flush=True)
    # Predeclared targets except for the two explicit 1500 candidates. Prefer the
    # extra node if it is within 25 Elo of the closest candidate's calibration error.
    chosen={target:profile for profile,(target,_,_) in PROFILES.items() if target!=1500}
    ranked=sorted(['p1500a','p1500b'],key=lambda p:abs(results[p]['local_reference_performance']-1500))
    selected=ranked[0]
    if abs(results['p1500b']['local_reference_performance']-1500)<=abs(results[selected]['local_reference_performance']-1500)+25:
        selected='p1500b'
    chosen[1500]=selected
    chosen[2100]='p2100s'
    chosen[2200]='p2100'
    chosen[2300]='p2300r'
    # These two cross-family candidates are assigned by their measured order,
    # not by the provisional target embedded in the opaque profile ID.
    middle=sorted(['p1900','p2000'],key=lambda p:results[p]['local_reference_performance'])
    chosen[1900],chosen[2000]=middle
    presets={}
    for target in sorted(chosen):
        profile=chosen[target];_,model,nodes=PROFILES[profile];result=results[profile]
        estimate=result['local_reference_performance'];interval=result['bootstrap_95_interval']
        presets[str(target)]={'profile':profile,'engine':model,'nodes':nodes,'estimate':estimate,
             'interval':interval,'games':48,'target_delta':estimate-target,
             'target_within_sampling_interval':interval[0]<=target<=interval[1]}
    document={'version':6,'created_utc':datetime.now(timezone.utc).isoformat(),
       'source':'calibration-v6','calibration_games':624,'kind':'Local SF UCI_Elo-reference estimates; not Chess.com/FIDE ratings',
       'selection':'Targets fixed at 1500–2300. For 1500 choose closest of two candidates, allowing 25 Elo tolerance for the extra-node candidate. Assign the two 1900/2000 candidates by their calibration estimate order. High-level refinement uses calibration results only. Each preset is locked before its own holdout games; no holdout results select its profile.',
       'presets':presets}
    (FOLDER/'summary.json').write_text(json.dumps({'config':json.loads((FOLDER/'config.json').read_text()),'results':results,'selection':document},indent=2)+'\n')
    (ROOT/'calibration-profiles.json').write_text(json.dumps(document,indent=2)+'\n')
    print('624 games audited; candidate preset map saved',flush=True)

if __name__=='__main__':main()
