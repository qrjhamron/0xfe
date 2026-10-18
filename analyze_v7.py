#!/usr/bin/env python3
"""Audit V7 calibration and write provisional runtime mappings."""
from datetime import datetime, timezone
import json, statistics
from pathlib import Path
import chess, chess.pgn
from calibrate_v7 import FOLDER, PROFILES, REFERENCES
from summarize_ratings import summarize

ROOT = Path(__file__).resolve().parent

def main():
    results = {}
    for profile, (target, model, nodes) in PROFILES.items():
        rows = [json.loads(x) for x in (FOLDER/(profile+'.jsonl')).read_text().splitlines() if x.strip()]
        assert len(rows) == 48 and all(r['dataset'] == 'calibration' for r in rows)
        assert {(r['opening'], r['white']) for r in rows} == {(i,c) for i in range(24) for c in (True,False)}
        with (FOLDER/(profile+'.pgn')).open() as f:
            for row in rows:
                game = chess.pgn.read_game(f); assert game and not game.errors
                assert game.headers['Profile'] == profile and int(game.headers['NodeBudget']) == nodes
                board = game.board()
                for move in game.mainline_moves(): assert move in board.legal_moves; board.push(move)
                assert board.ply() == row['plies']
            assert chess.pgn.read_game(f) is None
        result = summarize(rows)
        searches = [s for r in rows for s in r['searches']]
        observed = [s['nodes'] for s in searches if s['nodes'] is not None]
        result['node_budget'] = nodes
        result['search_stats'] = {'moves': len(searches), 'unknown_node_counts': len(searches)-len(observed),
            'node_shortfalls': sum(n < nodes for n in observed), 'p50_ms': round(statistics.median(s['ms'] for s in searches),2),
            'p95_ms': sorted(s['ms'] for s in searches)[int(.95*(len(searches)-1))],
            'min_reported_nodes': min(observed), 'max_reported_nodes': max(observed)}
        assert not result['search_stats']['unknown_node_counts']
        assert result['search_stats']['node_shortfalls'] < .05*len(searches)
        results[profile] = result
        print('AUDITED', profile, result['local_reference_performance'], result['bootstrap_95_interval'], flush=True)
    # Runtime stores base budgets and applies --node-multiplier 4. These estimates
    # were measured at the effective budget recorded in each calibration row.
    old = json.loads((ROOT/'calibration-profiles.json').read_text())['presets']
    presets = {}
    for target in sorted(old, key=int):
        profile = f'p{target}'; result = results[profile]
        # The runtime stores its base budget and applies --node-multiplier 4.
        base_nodes = PROFILES[profile][2] // 4
        presets[target] = {'profile': profile, 'engine': PROFILES[profile][1], 'nodes': base_nodes,
            'effective_nodes': PROFILES[profile][2], 'estimate': result['local_reference_performance'],
            'interval': result['bootstrap_95_interval'], 'games': 48,
            'target_delta': result['local_reference_performance']-int(target),
            'target_within_sampling_interval': result['bootstrap_95_interval'][0] <= int(target) <= result['bootstrap_95_interval'][1]}
    document = {'version': 7, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': 'calibration-v7', 'calibration_games': 432,
        'node_multiplier': 4, 'mode': 'single-pv',
        'kind': 'Local SF UCI_Elo-reference estimates; not Chess.com/FIDE ratings',
        'selection': 'The existing nine weight assignments were held fixed; only effective main-node budgets changed from the runtime 4x multiplier. Holdout results do not alter this mapping.',
        'presets': presets}
    (FOLDER/'summary.json').write_text(json.dumps({'config': json.loads((FOLDER/'config.json').read_text()), 'results': results, 'selection': document}, indent=2)+'\n')
    (FOLDER/'provisional-profiles.json').write_text(json.dumps(document, indent=2)+'\n')
    print('V7 calibration audited; provisional mapping saved', flush=True)

if __name__ == '__main__': main()
