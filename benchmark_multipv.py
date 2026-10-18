#!/usr/bin/env python3
"""Paired baseline vs Elo-bounded MultiPV benchmark for the fixed presets.

This is a local Stockfish-reference test. It is deliberately separate from
the runtime so a failed experiment cannot alter the calibrated profiles.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib, json, logging, math, random, time
from pathlib import Path
import chess, chess.engine, chess.pgn
from engine_runtime import engine_specs
from lc0_config import WEIGHTS
from presets import PRESETS
from rate_weights import OPENINGS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'multipv-benchmark'
REFERENCES=[1320,1700,2100,2500]
MODES=('single','multipv')

def book_plies(board, opening):
    for san in opening.split(): board.push_san(san)
    return board

def multipv_for_elo(elo):
    return 2 if elo<=1600 else 3 if elo<=1800 else 4 if elo<=2000 else 5 if elo<=2200 else 6

def choose(candidates, token, elo):
    valid=[c for c in candidates if c.get('move') and isinstance(c.get('score'),(int,float))]
    if not valid: return candidates[0]['move']
    top=max(c['score'] for c in valid)
    window=130 if elo<=1600 else 105 if elo<=1800 else 80 if elo<=2000 else 60 if elo<=2200 else 42
    temp=95 if elo<=1600 else 72 if elo<=1800 else 55 if elo<=2000 else 40 if elo<=2200 else 28
    pool=[c for c in valid if c['score']>=top-window]
    weights=[math.exp((c['score']-top)/temp) for c in pool]
    target=(int.from_bytes(hashlib.blake2s(token.encode(),digest_size=2).digest(),'big')/65536)*sum(weights)
    for c,w in zip(pool,weights):
        target-=w
        if target<=0:return c['move']
    return pool[0]['move']

def local_move(engine, board, mode, identity, elo, nodes, ply):
    started=time.monotonic();limit=chess.engine.Limit(nodes=nodes,time=2)
    if mode=='single':
        move=engine.play(board,limit,game=identity).move
        return move, (time.monotonic()-started)*1000, 1
    width=multipv_for_elo(elo)
    try:
        lines=engine.analyse(board,limit,multipv=width,game=identity,
                             info=chess.engine.INFO_SCORE|chess.engine.INFO_PV)
        candidates=[]
        for line in lines:
            pv=line.get('pv',[])
            if not pv or pv[0] not in board.legal_moves:continue
            score=line.get('score');
            candidates.append({'move':pv[0].uci(),'score':score.pov(board.turn).score(mate_score=100000) if score else None})
        if candidates:return chess.Move.from_uci(choose(candidates,f'{identity}:{ply}',elo)),(time.monotonic()-started)*1000,width
    except (chess.engine.EngineError,TimeoutError):
        pass
    return engine.play(board,limit,game=identity).move,(time.monotonic()-started)*1000,1

def play_game(profile, mode, index, white, lc0, sf):
    elo,engine_key,nodes=profile
    board=book_plies(chess.Board(),OPENINGS[index][1]); opening_plies=board.ply()
    reference=REFERENCES[index%len(REFERENCES)]; sf.configure({'UCI_Elo':reference})
    identity=f'{profile[0]}-{mode}-{index}-{int(white)}'; own_times=[]; widths=[]; start=time.monotonic(); termination=None
    while not board.is_game_over(claim_draw=True):
        if board.ply()>=300: termination='ply-cap';break
        if board.turn==white:
            move,ms,width=local_move(lc0,board,mode,identity,elo,nodes,board.ply());own_times.append(ms);widths.append(width)
        else:
            move=sf.play(board,chess.engine.Limit(time=.05),game=identity).move
        if move not in board.legal_moves: raise RuntimeError('illegal move')
        board.push(move)
    outcome=board.outcome(claim_draw=True)
    if outcome:
        result=outcome.result(); termination=outcome.termination.name.lower(); score=.5 if outcome.winner is None else int(outcome.winner==white)
    else: result='1/2-1/2';score=.5
    return {'profile':elo,'engine':engine_key,'nodes':nodes,'mode':mode,'opening':index,'opening_name':OPENINGS[index][0],
            'white':white,'reference_elo':reference,'score':score,'result':result,'termination':termination,
            'plies':board.ply(),'opening_plies':opening_plies,'seconds':round(time.monotonic()-start,3),
            'own_moves':len(own_times),'mean_own_ms':round(sum(own_times)/len(own_times),2) if own_times else None,
            'max_multipv':max(widths or [1])}

def run_profile(profile, folder, openings):
    elo,engine_key,nodes=profile;spec=engine_specs(str(ROOT/'runtime/stockfish'))[engine_key]
    path=folder/f'elo{elo}.jsonl';existing=[json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
    done={(r['mode'],r['opening'],r['white']) for r in existing}
    if len(done)>=len(MODES)*openings*2:
        return
    env=dict(__import__('os').environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    lc0=chess.engine.SimpleEngine.popen_uci(spec.command,timeout=20,env=env);sf=chess.engine.SimpleEngine.popen_uci(str(ROOT/'runtime/stockfish'),timeout=20,env=env)
    lc0.configure({'Threads':1,'MinibatchSize':1,'NNCacheSize':20000,'SmartPruningFactor':'0','RamLimitMb':128,'MaxPrefetch':0})
    sf.configure({'Threads':1,'Hash':16,'UCI_LimitStrength':True})
    try:
        with path.open('a') as out:
            for mode in MODES:
                for index in range(openings):
                    for white in (True,False):
                        if (mode,index,white) in done:continue
                        row=play_game(profile,mode,index,white,lc0,sf);out.write(json.dumps(row)+'\n');out.flush()
                        print(f'ELO{elo} {mode} {index+1}/{openings} {"W" if white else "B"} {row["result"]} {row["seconds"]}s',flush=True)
    finally:lc0.quit();sf.quit()

def fit(score,refs):
    if score<=0 or score>=len(refs):return None
    lo,hi=-2000.,6000.
    for _ in range(70):
        mid=(lo+hi)/2;expected=sum(1/(1+10**((r-mid)/400)) for r in refs)
        if expected<score:lo=mid
        else:hi=mid
    return (lo+hi)/2

def q(v,p):
    v=sorted(v);x=(len(v)-1)*p;a=int(x);b=min(a+1,len(v)-1);return v[a]*(b-x)+v[b]*(x-a)

def summarize(rows):
    result={}
    for mode in MODES:
        sub=[r for r in rows if r['mode']==mode];refs=[r['reference_elo'] for r in sub];score=sum(r['score'] for r in sub);result[mode]={'games':len(sub),'wins':sum(r['score']==1 for r in sub),'draws':sum(r['score']==.5 for r in sub),'losses':sum(r['score']==0 for r in sub),'points':score,'performance':round(fit(score,refs)) if fit(score,refs) is not None else None}
    paired=defaultdict(dict)
    for r in rows:paired[(r['opening'],r['white'])][r['mode']]=r['score']
    refs=[r['reference_elo'] for r in rows if r['mode']=='single'];base_score=sum(r['score'] for r in rows if r['mode']=='single');multi_score=sum(r['score'] for r in rows if r['mode']=='multipv')
    rng=random.Random(20261018);deltas=[]
    keys=list(paired)
    for _ in range(5000):
        b=m=0
        for _ in keys:
            k=rng.choice(keys);b+=paired[k]['single'];m+=paired[k]['multipv']
        deltas.append((fit(m,refs[:len(keys)]) or 0)-(fit(b,refs[:len(keys)]) or 0))
    result['delta']={'performance_change':round((fit(multi_score,refs) or 0)-(fit(base_score,refs) or 0)),'paired_bootstrap_95_interval':[round(q(deltas,.025)),round(q(deltas,.975))]}
    return result

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--openings',type=int,default=24,choices=range(6,25));ap.add_argument('--workers',type=int,default=2,choices=(1,2));args=ap.parse_args();args.output.mkdir(exist_ok=True)
    profiles=[(elo,PRESETS[elo].engine,PRESETS[elo].nodes) for elo in sorted(PRESETS)]
    config={'created_utc':datetime.now(timezone.utc).isoformat(),'profiles':profiles,'modes':MODES,'openings':args.openings,'references':REFERENCES,'stockfish_time':.05,'max_plies':300,'limitation':'Local Stockfish UCI_Elo references; not Chess.com/FIDE Elo.'}
    cfg=args.output/'config.json'
    if cfg.exists():
        old=json.loads(cfg.read_text());assert [tuple(x) for x in old['profiles']]==profiles and old['modes']==list(MODES) and old['openings']==args.openings and old['references']==REFERENCES
    else:cfg.write_text(json.dumps(config,indent=2))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fs=[ex.submit(run_profile,p,args.output,args.openings) for p in profiles]
        for f in as_completed(fs):f.result()
    all_rows={};summary={}
    for elo,_,_ in profiles:
        rows=[json.loads(x) for x in (args.output/f'elo{elo}.jsonl').read_text().splitlines() if x.strip()];all_rows[elo]=rows;summary[str(elo)]=summarize(rows)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    lines=['# MultiPV A/B benchmark','', '**Local Stockfish reference performance, not Chess.com/FIDE Elo.**','', '| Preset | Single-PV | Elo-bounded MultiPV | Change | 95% paired interval |','|---:|---:|---:|---:|---:|']
    for elo in sorted(summary):
        s=summary[elo];d=s['delta'];lines.append(f"| {elo} | {s['single']['performance']} | {s['multipv']['performance']} | {d['performance_change']:+d} | {d['paired_bootstrap_95_interval'][0]:+d} to {d['paired_bootstrap_95_interval'][1]:+d} |")
    lines += ['','The paired interval resamples identical opening/color pairs. A change whose interval crosses zero is not reliable under this sample. The benchmark controls weight, node budget, openings, colors, reference schedule, and hardware; it still cannot certify an online rating.','', '| Preset | Mode | Mean own-move ms | Median game seconds |','|---:|---|---:|---:|']
    for elo in sorted(summary):
        rows=[r for r in all_rows[int(elo)]]
        for mode in MODES:
            sub=[r for r in rows if r['mode']==mode]
            lines.append(f"| {elo} | {mode} | {sum(r['mean_own_ms'] for r in sub)/len(sub):.2f} | {sorted(r['seconds'] for r in sub)[len(sub)//2]:.2f} |")
    for elo in sorted(summary):
        s=summary[elo];lines.append(f"- {elo}: single {s['single']['wins']}–{s['single']['draws']}–{s['single']['losses']}; MultiPV {s['multipv']['wins']}–{s['multipv']['draws']}–{s['multipv']['losses']}")
    (args.output/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
