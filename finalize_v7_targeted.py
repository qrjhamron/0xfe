#!/usr/bin/env python3
"""Audit V7 holdout games and publish the calibrated runtime profiles."""
from datetime import datetime, timezone
import json
from pathlib import Path
import chess, chess.pgn
from calibrate_v7_targeted import FOLDER, PROFILES, ROOT
from summarize_ratings import summarize
from validate_v7_targeted import HOLDOUT, OUT

def audit_game_file(path, expected, profile, cases=None):
    rows=[json.loads(x) for x in path.with_suffix('.jsonl').read_text().splitlines() if x.strip()]
    assert len(rows)==expected
    with path.open() as f:
        for row in rows:
            game=chess.pgn.read_game(f); assert game and not game.errors
            assert game.headers['Profile']==profile and int(game.headers['NodeBudget'])==PROFILES[profile][2]
            board=game.board()
            for move in game.mainline_moves(): assert move in board.legal_moves; board.push(move)
            assert board.ply()==row['plies'] and game.headers['Result']==row['result']
            outcome=board.outcome(claim_draw=True)
            if row['termination']!='ply-cap':
                assert outcome and outcome.result()==row['result']
                assert row['score']==(.5 if outcome.winner is None else int(outcome.winner==row['white']))
        assert chess.pgn.read_game(f) is None
    return rows

def main():
    provisional=json.loads((FOLDER/'provisional-profiles.json').read_text())
    public={}; lines=['# V7 — kalibrasi node utama single-PV 1500–2300','',
      '**432 game kalibrasi + 108 game holdout = 540 game terverifikasi.**','',
      'Angka di bawah adalah performa relatif terhadap lawan Stockfish UCI_Elo lokal, bukan rating Chess.com/FIDE. '
      'Langkah utama memakai Lc0 single-PV pada node efektif yang dicatat; Stockfish tidak memakai MultiPV.','',
      '| Tombol | Node efektif | Estimasi gabungan | Interval 95% | Kalibrasi W–D–L | Holdout W–D–L |','|---:|---:|---:|---:|---:|---:|']
    for target, preset in sorted(provisional['presets'].items(), key=lambda x:int(x[0])):
        profile=preset['profile']; calibration=audit_game_file(FOLDER/(profile+'.pgn'),48,profile)
        holdout=audit_game_file(OUT/(profile+'.pgn'),12,profile)
        c=summarize(calibration); h=summarize(holdout)
        pooled=summarize(calibration+[{**r,'opening':r['opening']+100} for r in holdout])
        preset.update(estimate=pooled['local_reference_performance'], interval=pooled['bootstrap_95_interval'], games=60,
                      calibration_estimate=c['local_reference_performance'],
                      validation={'games':12,'wins':h['wins'],'draws':h['draws'],'losses':h['losses'],
                                  'estimate':h['local_reference_performance'],'interval':h['bootstrap_95_interval']},
                      target_delta=pooled['local_reference_performance']-int(target),
                      target_within_sampling_interval=pooled['bootstrap_95_interval'][0]<=int(target)<=pooled['bootstrap_95_interval'][1])
        public[target]={'estimate':preset['estimate'],'interval':preset['interval'],'games':60,
          'effective_nodes':preset['effective_nodes'],'calibration':c,'validation':preset['validation'],
          'target_delta':preset['target_delta'],'target_within_sampling_interval':preset['target_within_sampling_interval']}
        lines.append(f"| {target} | {preset['effective_nodes']} | {preset['estimate']} | {preset['interval'][0]}–{preset['interval'][1]} | {c['wins']}–{c['draws']}–{c['losses']} | {h['wins']}–{h['draws']}–{h['losses']} |")
    document=provisional; document['created_utc']=datetime.now(timezone.utc).isoformat(); document['total_games']=540
    document['holdout_games']=108; document['note']='Fixed buttons are nominal training targets. Estimates are local Stockfish-reference measurements, not certified human ratings.'
    (ROOT/'calibration-profiles.json').write_text(json.dumps(document,indent=2)+'\n')
    (FOLDER/'public-results.json').write_text(json.dumps({'created_utc':document['created_utc'],'calibration_games':432,'holdout_games':108,'total_verified_games':540,'presets':public,'limitation':document['note']},indent=2)+'\n')
    lines += ['', 'Target di luar interval diberi status tentatif; interval hanya mengukur variasi sampel. Holdout tidak dipakai untuk mengganti model atau node.', '']
    for target,row in public.items(): lines.append(f"- {target}: delta {row['target_delta']:+d}; target dalam interval: {'ya' if row['target_within_sampling_interval'] else 'tidak'}.")
    (FOLDER/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('V7 FINALIZED: 540 verified games',flush=True)

if __name__=='__main__': main()
