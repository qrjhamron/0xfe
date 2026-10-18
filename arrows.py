#!/usr/bin/env python3
"""Local move recommendations with fixed training levels."""
import argparse
from dataclasses import replace
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import time
from urllib.parse import urlsplit
import uuid
import math

import chess
from playwright.sync_api import sync_playwright, Error as BrowserError
from engine_runtime import EnginePool, Request, engine_specs
from auto_moves import AutoMoves
from premove import Premove
from session_audit import SessionAudit
from presets import PRESETS, CONFIG_ID, resolve_preset, public_presets
from opening_book import lookup as opening_lookup
from adaptive_strength import budget_for_position
from app_paths import ROOT

POLL = """() => {const a=window.__chessArrowCoach;
return {version:a?.version,configId:a?.configId,snapshot:a?.poll?.()};}"""

def multipv_for_elo(elo):
    """Bound human-like choice set; higher levels see more candidates but remain capped."""
    return 2 if elo<=1600 else 3 if elo<=1800 else 4 if elo<=2000 else 5 if elo<=2200 else 6

def scaled_nodes(nodes, multiplier):
    """Increase the main Lc0 search budget without changing the Elo selector."""
    return min(256, max(1, int(nodes * multiplier)))


def effective_budget(snapshot, preset, node_multiplier=1.0):
    """Apply the optional phase policy after the calibrated preset/multiplier."""
    base = scaled_nodes(preset.nodes, node_multiplier) if node_multiplier != 1 else preset.nodes
    budget = budget_for_position(chess.Board(snapshot['fen']), base,
                                 bool(snapshot.get('prefs', {}).get('adaptiveStrength', True)))
    return replace(preset, nodes=budget.nodes), budget

def choose_candidate(request, result):
    candidates=result.get('candidates') or []
    if len(candidates)<2:
        return result.get('move'), 'engine'
    scored=[c for c in candidates if c.get('move') and isinstance(c.get('score_cp'),(int,float))]
    if not scored:
        return result.get('move'), 'engine'
    top=max(c['score_cp'] for c in scored)
    # Elo-limited window: lower levels may choose a plausible second/third move,
    # while high levels stay close to the principal variation.
    window=130 if request.elo<=1600 else 105 if request.elo<=1800 else 80 if request.elo<=2000 else 60 if request.elo<=2200 else 42
    pool=[c for c in scored if c['score_cp']>=top-window]
    temp=95 if request.elo<=1600 else 72 if request.elo<=1800 else 55 if request.elo<=2000 else 40 if request.elo<=2200 else 28
    weights=[math.exp((c['score_cp']-top)/temp) for c in pool]
    digest=hashlib.blake2s(request.token.encode(),digest_size=2).digest()
    target=(int.from_bytes(digest,'big')/65536)*sum(weights)
    for candidate,weight in zip(pool,weights):
        target-=weight
        if target<=0:
            return candidate['move'], f"hybrid-multipv-{len(candidates)}"
    return pool[0]['move'], f"hybrid-multipv-{len(candidates)}"


class InstanceLock:
    """The OS releases the daemon lock even when its process crashes."""
    def __enter__(self):
        folder = ROOT / 'runtime'
        folder.mkdir(exist_ok=True)
        self.file = (folder / 'daemon.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b'0'); self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('A coach daemon is already running in this installation.')
        return self

    def __exit__(self, *_):
        self.file.close()


def write_status(path, status):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(status, indent=2))
        temp.replace(path)
    except OSError as exc:
        logging.warning('Status file unavailable (%s)', type(exc).__name__)


def run(args, specs):
    overlay = (ROOT / 'overlay.js').read_text()
    panel = (ROOT / 'panel.js').read_text()
    availability=''.join('1' if specs[p.engine].available else '0' for p in PRESETS.values())
    assets_id=hashlib.sha256((panel+overlay).encode()).hexdigest()[:12]
    panel_id=f'{CONFIG_ID}:{availability}:{assets_id}'
    panel_options = {'defaults': {'elo': args.elo, 'bothSides': args.both_sides},
                     'presets': public_presets(specs), 'configId': panel_id}
    pool = EnginePool(specs, think=args.think, threads=args.threads, hash_mb=args.hash_mb,
                      cache_size=args.cache_size)
    records = {}
    browser = None
    try:
        with sync_playwright() as pw:
            while True:
                try:
                    if browser is None or not browser.is_connected():
                        browser = pw.chromium.connect_over_cdp(args.cdp, timeout=5000)
                        browser_session = browser.new_browser_cdp_session()
                        for state in records.values():
                            pool.cancel(state['owner'])
                            pool.cancel(state['premove'].owner)
                        records.clear()
                        logging.info('Browser connected; responsive engine workers enabled')
                    # Pump CDP events even when every current tab is outside chess pages.
                    browser_session.send('Target.getTargets')
                    pages = [page for ctx in browser.contexts for page in ctx.pages]
                    for page in list(records):
                        if page not in pages or page.is_closed():
                            removed=records.pop(page)
                            pool.cancel(removed['owner'])
                            pool.cancel(removed['premove'].owner)
                    active = False
                    for page in pages:
                        url = urlsplit(page.url)
                        if page.is_closed() or url.hostname not in ('www.chess.com', 'chess.com'):
                            continue
                        if not url.path.startswith(('/game/', '/play/', '/analysis')):
                            continue
                        if page not in records:
                            records[page] = {'owner':uuid.uuid4().hex,'pending':None,'render':None,
                                             'retry_at':0,'failures':0,'automation':AutoMoves(),
                                             'premove':Premove(),'audit':SessionAudit(args.audit_dir)}
                        state = records[page]
                        try:
                            response = page.evaluate(POLL)
                            snapshot = response.get('snapshot')
                            if response.get('version') != 11 or response.get('configId') != panel_id:
                                snapshot = page.evaluate(panel, panel_options)
                            if snapshot:
                                native_audit=page.evaluate('()=>window.__chessArrowCoach?.audit()')
                                state['audit'].sync(snapshot,native_audit,page.url)
                            native=snapshot.get('native',{}) if snapshot else {}
                            planner=state['premove']
                            preset_for_game = (resolve_preset(snapshot['prefs']['elo'], specs)
                                if snapshot else None)
                            phase_budget = None
                            if preset_for_game and snapshot:
                                preset_for_game, phase_budget = effective_budget(
                                    snapshot, preset_for_game, args.node_multiplier)
                            prepared = planner.update(snapshot, pool, preset_for_game)
                            if snapshot:
                                page.evaluate('p=>window.__chessArrowCoach?.premoveState(p)',
                                              {**planner.public_state(),'token':snapshot['token']})
                            if prepared and snapshot['eligible']:
                                board = chess.Board(snapshot['fen'])
                                payload = {'fen':snapshot['fen'], 'move':prepared,
                                              'elo':snapshot['prefs']['elo'], 'san':board.san(chess.Move.from_uci(prepared)),
                                    'token':snapshot['token'], 'latency_ms':0, 'cached':True}
                                if page.evaluate(overlay,payload):
                                    state['render']=payload
                            if snapshot and native.get('supported') and snapshot['reason']=='opponent' and planner.plan:
                                accepted=page.evaluate('p=>window.__chessArrowCoach?.queueNative(p)',
                                    {'base':snapshot['fen'],'token':snapshot['token'],'plan':planner.plan})
                                signature=(snapshot['token'],tuple(x['move'] for x in planner.plan))
                                if accepted and state.get('native_signature')!=signature:
                                    state['native_signature']=signature
                                    write_status(args.status,{'native_premove':True,'base':snapshot['fen'],
                                        'plan':planner.plan,'elo':snapshot['prefs']['elo'],
                                        'gameId':snapshot['gameId'],'branches':planner.public_state(),
                                        'updated_at':time.time(),'url':page.url.split('?',1)[0]})
                                    logging.info('Native premove queued: %s',len(planner.plan))
                                snapshot=page.evaluate('()=>window.__chessArrowCoach?.read()')
                            state['automation'].tick(page, snapshot, state.get('render'))
                            if not snapshot or not snapshot['eligible'] or chess.Board(snapshot['fen']).is_game_over():
                                pool.cancel(state['owner'])
                                state.update(pending=None, render=None)
                                continue
                            active = True
                            elo = snapshot['prefs']['elo']
                            preset = preset_for_game or resolve_preset(elo, specs)
                            model = preset.engine
                            token = snapshot['token']
                            if state.get('token') != token:
                                pool.cancel(state['owner'])
                                state.update(token=token, pending=None, render=state.get('render') if prepared else None, retry_at=0, failures=0)
                            # A tiny book handles only common, non-tactical opening plies.
                            book_move=opening_lookup(chess.Board(snapshot['fen']), snapshot.get('history',()),
                                                     snapshot.get('prefs',{}).get('openingBook',True))
                            if book_move and state.get('book_token')!=token:
                                board=chess.Board(snapshot['fen'])
                                state['render']={'fen':snapshot['fen'],'move':book_move,'elo':elo,
                                                  'san':board.san(chess.Move.from_uci(book_move)),'token':token,
                                                  'latency_ms':0,'cached':True,'source':'opening-book'}
                                state['book_token']=token
                            rendered = state['render']
                            if rendered and rendered['token'] == token:
                                if not snapshot.get('rendered'):
                                    page.evaluate(overlay, rendered)
                                continue
                            if state['pending'] == token or time.monotonic() < state['retry_at']:
                                continue
                            # Main moves always use one policy line. MultiPV scores are
                            # useful for premove branch coverage, but selecting directly
                            # from them made the human-trained Lc0 policy less stable.
                            # Keep Stockfish single-PV too; its Elo limiter still applies.
                            analysis_mode = False
                            request = Request(owner=state['owner'], token=token,
                                              game=snapshot['gameId'], fen=snapshot['fen'], elo=elo,
                                              root_fen=snapshot.get('rootFen', ''),
                                              history=tuple(snapshot.get('history', ())),
                                              nodes=preset.nodes,
                                              analysis=analysis_mode, multipv=1,
                                              phase=phase_budget.phase if phase_budget else 'fixed',
                                              base_nodes=(scaled_nodes(resolve_preset(elo, specs).nodes,
                                                                       args.node_multiplier)
                                                          if phase_budget else preset.nodes))
                            pool.submit(model, request)
                            state.update(pending=token, render=None)
                            page.evaluate('p=>window.__chessArrowCoach?.progress(p)',
                                          {'token': token, 'message': f"Menyiapkan rekomendasi Elo {elo}…"})
                        except (BrowserError, ValueError, KeyError) as exc:
                            pool.cancel(state['owner'])
                            state.update(pending=None, render=None)
                            pool.cancel(state['premove'].owner)
                            state['premove'].reset()
                            logging.debug('Board changed (%s)', type(exc).__name__)
                    owners = {state['owner']: (page, state) for page, state in records.items()}
                    planners={state['premove'].owner:state['premove'] for state in records.values()}
                    for result in pool.drain():
                        request = result['request']
                        if request.owner in planners:
                            planners[request.owner].accept(result,pool)
                            continue
                        if request.owner not in owners:
                            continue
                        page, state = owners[request.owner]
                        if page.is_closed() or state['pending'] != request.token:
                            continue
                        state['pending'] = None
                        if result.get('error') or not result.get('move'):
                            state['failures'] += 1
                            state['retry_at'] = time.monotonic() + min(15, 2 ** min(state['failures'], 4))
                            try:
                                page.evaluate('p=>window.__chessArrowCoach?.progress(p)',
                                              {'token': request.token, 'error': 'Rekomendasi belum siap. Mencoba lagi…'})
                            except BrowserError:
                                pass
                            continue
                        chosen,source=choose_candidate(request,result)
                        if not chosen:
                            continue
                        move = chess.Move.from_uci(chosen)
                        board = chess.Board(request.fen)
                        if move not in board.legal_moves:
                            continue
                        payload = {'fen': request.fen, 'move': move.uci(), 'elo': request.elo,
                                   'san': board.san(move), 'token': request.token,
                                   'latency_ms': result['latency_ms'],
                                   'cached': result['cached'],'source':source,
                                   'multipv':request.multipv,
                                   'candidates':result.get('candidates',[])}
                        payload.update({'phase': request.phase,
                                        'nodes_base': request.base_nodes or request.nodes,
                                        'nodes_effective': request.nodes,
                                        'adaptive_strength': request.phase != 'fixed'})
                        try:
                            if not page.evaluate(overlay, payload):
                                continue
                        except BrowserError:
                            continue
                        state.update(render=payload, failures=0, retry_at=0)
                        worker = pool.workers[result['engine']]
                        write_status(args.status, {**payload, 'engine': result['engine'], 'nodes': request.nodes, 'updated_at': time.time(),
                                                  'url': page.url.split('?', 1)[0],
                                                  'strength_limited': result['engine'] == 'stockfish',
                                                  'threads': args.threads, 'hash_mb': args.hash_mb,
                                                  'node_multiplier': args.node_multiplier,
                                                  'phase': payload.get('phase', 'fixed'),
                                                  'nodes_base': payload.get('nodes_base', request.nodes),
                                                  'metrics': dict(worker.metrics)})
                        logging.info('%s %s: %s · %s ms%s', specs[result['engine']].label,
                                     f'{request.nodes} nodes' if specs[result['engine']].kind == 'nodes' else f'Elo {request.elo}', payload['san'], result['latency_ms'],
                                     ' (cache)' if result['cached'] else '')
                    moving=any(s['automation'].job for s in records.values())
                    predicting=any(s['premove'].pending or s['premove'].screen for s in records.values())
                    time.sleep(.015 if moving else .05 if active or predicting else .2)
                except BrowserError as exc:
                    logging.warning('Waiting for browser (%s)', type(exc).__name__)
                    browser = None
                    time.sleep(2)
    finally:
        pool.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cdp', default=os.getenv('CHESS_CDP', 'http://127.0.0.1:9222'))
    parser.add_argument('--engine', default=os.getenv('STOCKFISH_PATH'))
    parser.add_argument('--elo', type=int, choices=list(PRESETS), default=1500)
    parser.add_argument('--think', type=float, default=.4)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--hash-mb', type=int, default=64)
    parser.add_argument('--cache-size', type=int, default=128)
    parser.add_argument('--node-multiplier', type=float, default=1.0,
                        help='Multiply the main Lc0 node budget; main moves stay single-PV (default: 1).')
    parser.add_argument('--both-sides', action='store_true')
    parser.add_argument('--status', type=Path, default=ROOT / 'status.json')
    parser.add_argument('--audit-dir', type=Path, default=ROOT / 'runtime/games')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    configured = ROOT / 'runtime' / ('stockfish.exe' if os.name == 'nt' else 'stockfish')
    path = args.engine or (str(configured) if configured.exists() else shutil.which('stockfish'))
    if not path:
        parser.error('Stockfish missing. Run install.py or pass --engine PATH.')
    if (not .05 <= args.think <= 10 or not 1 <= args.threads <= 8 or
            not 16 <= args.hash_mb <= 512 or not 1 <= args.cache_size <= 1024 or
            not 1 <= args.node_multiplier <= 32):
        parser.error('Use --think .05–10, --threads 1–8, --hash-mb 16–512, --cache-size 1–1024, --node-multiplier 1–32.')
    specs = engine_specs(path)
    try:
        resolve_preset(args.elo, specs)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        with InstanceLock():
            run(args, specs)
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    def stop(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        main()
    except KeyboardInterrupt:
        pass
