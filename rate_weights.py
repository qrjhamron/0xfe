#!/usr/bin/env python3
"""Local Gyal/SF-limited-strength tournament. Results are NOT Chess.com Elo."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time

import chess
import chess.engine
import chess.pgn
from engine_runtime import engine_specs
from lc0_config import WEIGHTS

ROOT = Path(__file__).resolve().parent
# Original hand-selected opening lines; no opening-book download required.
OPENINGS = [
 ('Ruy Lopez','e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6'),
 ('Italian','e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6'),
 ('Scotch','e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Bc5'),
 ('Petrov','e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4'),
 ('Vienna','e4 e5 Nc3 Nf6 f4 d5'),
 ('Najdorf','e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6'),
 ('Classical Sicilian','e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 d6'),
 ('Alapin','e4 c5 c3 Nf6 e5 Nd5 d4 cxd4'),
 ('French advance','e4 e6 d4 d5 e5 c5 c3 Nc6'),
 ('French Tarrasch','e4 e6 d4 d5 Nd2 Nf6 e5 Nfd7'),
 ('Caro-Kann classical','e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5'),
 ('Caro-Kann advance','e4 c6 d4 d5 e5 Bf5 Nf3 e6'),
 ('Scandinavian','e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6'),
 ('Pirc','e4 d6 d4 Nf6 Nc3 g6 Nf3 Bg7'),
 ('Queens gambit declined','d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7'),
 ('Slav','d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4'),
 ('Nimzo-Indian','d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O'),
 ('Kings Indian','d4 Nf6 c4 g6 Nc3 Bg7 e4 d6'),
 ('Grunfeld','d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5'),
 ('Catalan','d4 Nf6 c4 e6 g3 d5 Bg2 Be7'),
 ('English symmetric','c4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7'),
 ('English reversed Sicilian','c4 e5 Nc3 Nf6 g3 d5 cxd5 Nxd5'),
 ('Reti','Nf3 d5 g3 Nf6 Bg2 e6 O-O Be7'),
 ('London','d4 d5 Nf3 Nf6 Bf4 e6 e3 c5'),
]
RATINGS = [1320,1600,1900,2200]


def opening_board(index):
    board = chess.Board()
    for san in OPENINGS[index][1].split():
        board.push_san(san)
    return board


def play_game(lc0, stockfish, key, index, white, think, max_plies, nodes=1):
    board = opening_board(index)
    opening_plies = board.ply()
    rating = RATINGS[index % len(RATINGS)]
    stockfish.configure({'UCI_Elo':rating})
    identity = f'{key}-{index}-{int(white)}'
    started = time.monotonic()
    termination = None
    # No evaluation adjudication: only chess rules or an explicitly marked cap.
    while not board.is_game_over(claim_draw=True):
        if board.ply() >= max_plies:
            termination = 'ply-cap'; break
        engine = lc0 if board.turn == white else stockfish
        limit = chess.engine.Limit(nodes=nodes,time=2) if engine is lc0 else chess.engine.Limit(time=think)
        result = engine.play(board,limit,game=identity)
        if result.move not in board.legal_moves:
            raise RuntimeError('Engine returned an illegal move: '+identity)
        board.push(result.move)
    outcome = board.outcome(claim_draw=True)
    if outcome:
        termination = outcome.termination.name.lower()
        result_string = outcome.result()
        score = .5 if outcome.winner is None else int(outcome.winner == white)
    else:
        result_string = '1/2-1/2'; score = .5
    game = chess.pgn.Game.from_board(board)
    game.headers.update({'Event':f'Local Gyal {nodes}-node calibration', 'Site':'Local CPU',
        'Date':datetime.now(timezone.utc).strftime('%Y.%m.%d'), 'Round':str(index+1),
        'White':WEIGHTS[key][0] if white else f'Stockfish 19 UCI_Elo {rating}',
        'Black':f'Stockfish 19 UCI_Elo {rating}' if white else WEIGHTS[key][0],
        'Result':result_string,'Opening':OPENINGS[index][0], 'Termination':termination,
        'GyalNodes':str(nodes),'StockfishMoveTime':str(think), 'ReferenceElo':str(rating)})
    if termination == 'ply-cap':
        game.end().comment = 'Administrative draw at ply cap; not a rule-based draw.'
    return {'nodes':nodes,'weight':key,'opening':index,'opening_name':OPENINGS[index][0],
        'white':white,'reference_elo':rating,'score':score,'result':result_string,
        'termination':termination,'plies':board.ply(),'opening_plies':opening_plies,
        'seconds':round(time.monotonic()-started,2),'pgn':str(game)}


def run_weight(key,args):
    specs=engine_specs(str(ROOT/'runtime/stockfish'))
    lc0=chess.engine.SimpleEngine.popen_uci(specs[key].command,timeout=20)
    stockfish=chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'),timeout=20)
    lc0.configure({'Threads':1,'MinibatchSize':1,'NNCacheSize':20000,
                   'SmartPruningFactor':'0','RamLimitMb':128})
    stockfish.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
    folder=args.output; path=folder/(key+'.jsonl'); pgn=folder/(key+'.pgn')
    existing=[]
    if path.exists():
        existing=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    finished={(r['opening'],r['white']) for r in existing}
    try:
        for index in range(args.openings):
            for white in [True,False]:
                if (index,white) in finished:continue
                row=play_game(lc0,stockfish,key,index,white,args.think,args.max_plies,args.nodes)
                with pgn.open('a') as f:f.write(row.pop('pgn')+'\n\n')
                with path.open('a') as f:f.write(json.dumps(row)+'\n')
                existing.append(row)
                wins=sum(r['score']==1 for r in existing);draws=sum(r['score']==.5 for r in existing)
                print(f'{key} {len(existing)}/{args.openings*2}: W{wins} D{draws} L{len(existing)-wins-draws}; '
                      f'last vs {row["reference_elo"]}, {row["result"]}, {row["termination"]}, '
                      f'{row["plies"]} plies, {row["seconds"]}s',flush=True)
    finally:
        lc0.quit();stockfish.quit()
    return existing


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--nodes',type=int,default=1,choices=range(1,257))
    parser.add_argument('--think',type=float,default=.05)
    parser.add_argument('--max-plies',type=int,default=300)
    parser.add_argument('--openings',type=int,default=24,choices=range(1,25))
    parser.add_argument('--workers',type=int,default=2,choices=[1,2])
    args=parser.parse_args()
    if args.output is None:
        args.output=ROOT/('rating-results' if args.nodes==1 else f'rating-results-node{args.nodes}')
    logging.getLogger('chess.engine').setLevel(logging.ERROR)
    for i in range(len(OPENINGS)):opening_board(i)
    args.output.mkdir(parents=True,exist_ok=True)
    config={'created_utc':datetime.now(timezone.utc).isoformat(),
        'nodes':args.nodes,
        'lc0':f'v0.32.1, Eigen CPU, 1 thread, nodes={args.nodes}, movetime ceiling=2s, minibatch=1, nncache=20000, SmartPruningFactor=0, RamLimitMb=128',
        'stockfish':'Stockfish 19, 1 thread, Hash=16 MiB, UCI_LimitStrength=true',
        'stockfish_move_seconds':args.think,'references':RATINGS,
        'max_plies':args.max_plies,'opening_pairs_per_weight':args.openings,
        'draws':'claimable threefold/50-move draws claimed; no evaluation adjudication; administrative ply-cap draws separately identified',
        'limitation':'Local SF UCI_Elo-reference performance only, not calibrated Chess.com/FIDE Elo. Bootstrap covers game sampling, not reference/clock systematic bias.'}
    config_path=args.output/'config.json'
    if config_path.exists():
        previous=json.loads(config_path.read_text())
        for key in ['lc0','stockfish','stockfish_move_seconds','references','max_plies','opening_pairs_per_weight']:
            if previous[key]!=config[key]:raise ValueError('Cannot resume with changed config: '+key)
    else:config_path.write_text(json.dumps(config,indent=2))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        tasks={executor.submit(run_weight,key,args):key for key in WEIGHTS}
        for task in as_completed(tasks):
            rows=task.result();print('COMPLETE',tasks[task],len(rows),flush=True)
    print('TOURNAMENT COMPLETE',flush=True)

if __name__=='__main__':main()
