#!/usr/bin/env python3
"""Verify saved tournament PGNs against every JSONL game record."""
from pathlib import Path
import json
import argparse
import chess.pgn
from rate_weights import OPENINGS, RATINGS, opening_board
from lc0_config import WEIGHTS
ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,default=ROOT/'rating-results')
    args=parser.parse_args()
    folder=args.folder
    config=json.loads((folder/'config.json').read_text())
    pairs=config['opening_pairs_per_weight'];nodes=config.get('nodes',1)
    total=0
    for key,(label,*_) in WEIGHTS.items():
        rows=[json.loads(x) for x in (folder/(key+'.jsonl')).read_text().splitlines()]
        assert len(rows)==pairs*2
        assert {(r['opening'],r['white']) for r in rows}=={(i,c) for i in range(pairs) for c in [True,False]}
        with (folder/(key+'.pgn')).open() as source:
            for row in rows:
                game=chess.pgn.read_game(source)
                assert game and not game.errors
                assert int(game.headers['GyalNodes'])==nodes
                assert row.get('nodes',1)==nodes
                assert game.headers['Result']==row['result']
                assert game.headers['Opening']==OPENINGS[row['opening']][0]
                assert (game.headers['White']==label)==row['white']
                assert int(game.headers['ReferenceElo'])==RATINGS[row['opening']%4]
                board=game.board()
                for move in game.mainline_moves():
                    assert move in board.legal_moves
                    board.push(move)
                    if board.ply()==row['opening_plies']:
                        assert board.fen()==opening_board(row['opening']).fen()
                assert board.ply()==row['plies']
                outcome=board.outcome(claim_draw=True)
                if row['termination']!='ply-cap':
                    assert outcome and outcome.result()==row['result']
                    assert outcome.termination.name.lower()==row['termination']
                    score=.5 if outcome.winner is None else int(outcome.winner==row['white'])
                    assert score==row['score']
                total+=1
            assert chess.pgn.read_game(source) is None
        print('PASS',key,f'{pairs*2} PGNs: legal moves, opening/color coverage, real chess-rule results',flush=True)
    print('VERIFIED',total,'games',flush=True)

if __name__=='__main__':main()
