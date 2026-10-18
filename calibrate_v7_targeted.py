#!/usr/bin/env python3
"""Calibrate the runtime's 4x-main-node single-PV profiles."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib, json, logging, os, time
from pathlib import Path
import chess, chess.engine, chess.pgn
from engine_runtime import engine_specs
from rate_weights import OPENINGS, opening_board

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'calibration-v7-targeted'
REFERENCES = [1320, 1700, 2100, 2500]
# These are the effective main-move budgets used by the running daemon.
PROFILES = {
    'p1500': (1500, 'meangirl7', 2),
    'p1600': (1600, 'meangirl7', 4),
    'p1700': (1700, 'evilgyal6', 8),
    'p1800': (1800, 'goodgyal5', 8),
    'p1900': (1900, 'goodgyal5', 12),
    'p2000': (2000, 'badgyal8', 4),
    'p2100': (2100, 'badgyal8', 6),
    'p2200': (2200, 'badgyal8', 10),
    'p2300': (2300, 'badgyal8', 24),
}
OPTIONS = {'Threads': 1, 'MinibatchSize': 1, 'NNCacheSize': 20000,
           'SmartPruningFactor': '0', 'RamLimitMb': 128, 'MaxPrefetch': 0}


def play_game(lc0, sf, profile, index, white, opening_override=None,
              reference_override=None, dataset='calibration'):
    target, model, nodes = PROFILES[profile]
    if opening_override is None:
        board = opening_board(index); opening_name = OPENINGS[index][0]
    else:
        board = chess.Board(); opening_name = opening_override[0]
        for san in opening_override[1].split(): board.push_san(san)
    opening_plies = board.ply()
    reference = REFERENCES[index % 4] if reference_override is None else reference_override
    sf.configure({'UCI_Elo': reference})
    identity = f'{profile}-{dataset}-{index}-{int(white)}'
    started = time.monotonic(); measurements = []; termination = None
    while not board.is_game_over(claim_draw=True):
        if board.ply() >= 300:
            termination = 'ply-cap'; break
        ours = board.turn == white; engine = lc0 if ours else sf
        limit = chess.engine.Limit(nodes=nodes, time=2) if ours else chess.engine.Limit(time=.05)
        t = time.monotonic()
        result = engine.play(board, limit, game=identity,
                             info=chess.engine.INFO_BASIC if ours else chess.engine.INFO_NONE)
        if result.move not in board.legal_moves: raise RuntimeError('Illegal move: '+identity)
        if ours: measurements.append({'nodes': result.info.get('nodes'),
                                      'ms': round((time.monotonic()-t)*1000, 2)})
        board.push(result.move)
    outcome = board.outcome(claim_draw=True)
    if outcome:
        result_string = outcome.result(); termination = outcome.termination.name.lower()
        score = .5 if outcome.winner is None else int(outcome.winner == white)
    else: result_string, score = '1/2-1/2', .5
    game = chess.pgn.Game.from_board(board)
    game.headers.update({'Event': 'V7 targeted main-node single-PV calibration', 'Site': 'Local CPU',
        'Date': datetime.now(timezone.utc).strftime('%Y.%m.%d'), 'Round': str(index+1),
        'White': profile if white else f'Stockfish UCI_Elo {reference}',
        'Black': f'Stockfish UCI_Elo {reference}' if white else profile,
        'Result': result_string, 'Opening': opening_name, 'Termination': termination,
        'Profile': profile, 'NodeBudget': str(nodes), 'ReferenceElo': str(reference),
        'StockfishMoveTime': '0.05', 'MaxPrefetch': '0', 'Mode': 'single-pv'})
    if termination == 'ply-cap': game.end().comment = 'Administrative draw at 300 ply.'
    row = {'profile': profile, 'target': target, 'nodes': nodes, 'opening': index,
           'opening_plies': opening_plies, 'white': white, 'reference_elo': reference,
           'score': score, 'result': result_string, 'termination': termination,
           'plies': board.ply(), 'seconds': round(time.monotonic()-started, 2),
           'searches': measurements, 'dataset': dataset}
    return row, str(game)


def run_profile(profile, folder, openings=24, dataset='calibration', cases=None):
    _, model, _ = PROFILES[profile]
    spec = engine_specs(str(ROOT/'runtime/stockfish'))[model]
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    lc0 = chess.engine.SimpleEngine.popen_uci(spec.command, timeout=20, env=environment)
    sf = chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'), timeout=20, env=environment)
    lc0.configure(OPTIONS); sf.configure({'Threads': 1, 'Hash': 16, 'UCI_LimitStrength': True})
    path = folder/(profile+'.jsonl'); pgn = folder/(profile+'.pgn')
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
    try:
        iterable = range(openings) if cases is None else range(len(cases))
        done = {(r['opening'], r['white']) for r in rows if r.get('dataset', dataset) == dataset}
        for index in iterable:
            opening = None if cases is None else cases[index]
            for white in (True, False):
                if (index, white) in done: continue
                row, game = play_game(lc0, sf, profile, index, white, opening,
                                      None if cases is None else [1320,1700][index % 2], dataset)
                with pgn.open('a') as f: f.write(game+'\n\n')
                with path.open('a') as f: f.write(json.dumps(row)+'\n')
                rows.append(row)
                w = sum(r['score'] == 1 for r in rows if r.get('dataset', dataset) == dataset)
                d = sum(r['score'] == .5 for r in rows if r.get('dataset', dataset) == dataset)
                print(f'{profile} {dataset} {index+1}/{len(list(iterable))} '
                      f'W{w} D{d} L{len([r for r in rows if r.get("dataset", dataset)==dataset])-w-d} '
                      f'{row["result"]} {row["seconds"]}s', flush=True)
    finally:
        lc0.quit(); sf.quit()
    return profile


def run_all(folder=FOLDER):
    folder.mkdir(exist_ok=True)
    config = {'version': 7, 'profiles': PROFILES, 'references': REFERENCES,
              'engine_options': OPTIONS, 'stockfish_seconds': .05,
              'games_per_profile': 48, 'opening_pairs': 24, 'max_plies': 300,
              'mode': 'single-pv', 'node_multiplier': 1,
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'limitation': 'Local Stockfish UCI_Elo reference; not Chess.com/FIDE Elo.',
              'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in [ROOT/'runtime/lc0', ROOT/'runtime/stockfish',
                                   *sorted((ROOT/'runtime/lc0-weights').glob('*.pb.gz'))]}}
    cfg = folder/'config.json'
    if cfg.exists():
        old = json.loads(cfg.read_text())
        assert old['profiles'] == {k:list(v) for k,v in PROFILES.items()} or old['profiles'] == PROFILES
    else: cfg.write_text(json.dumps(config, indent=2)+'\n')
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_profile, profile, folder) for profile in PROFILES]
        for future in as_completed(futures): print('COMPLETE', future.result(), flush=True)
    assert all(len((folder/(p+'.jsonl')).read_text().splitlines()) == 48 for p in PROFILES)
    print('V7 CALIBRATION COMPLETE: 432 games', flush=True)


if __name__ == '__main__':
    logging.getLogger('chess.engine').setLevel(logging.ERROR)
    run_all()
