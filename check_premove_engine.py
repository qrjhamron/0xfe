"""Real persistent-engine verification of branch searches and cache separation."""
from dataclasses import replace
from pathlib import Path
import time
import chess
from engine_runtime import EnginePool, Request, engine_specs
from presets import resolve_preset
from premove import Premove


def wait(pool, token):
    end=time.monotonic()+30
    while time.monotonic()<end:
        for r in pool.drain():
            if r['request'].token==token:
                assert not r.get('error'),r
                return r
        time.sleep(.01)
    raise AssertionError('Engine response timed out')


def main():
    root=Path(__file__).resolve().parent
    specs=engine_specs(str(root/'runtime/stockfish'))
    preset=resolve_preset(1500,specs)
    pool=EnginePool(specs,threads=1,hash_mb=64,cache_size=64)
    try:
        req=Request('cache-check','analysis','test',chess.STARTING_FEN,1500,
                    nodes=64,analysis=True,multipv=5)
        pool.submit(preset.engine,req);r=wait(pool,req.token)
        assert len(r['candidates'])>=3
        assert len({x['move'] for x in r['candidates']})==len(r['candidates'])
        for x in r['candidates']:assert chess.Move.from_uci(x['move']) in chess.Board().legal_moves
        repeat=replace(req,token='analysis-repeat');pool.submit(preset.engine,repeat)
        assert wait(pool,repeat.token)['cached']
        own=replace(req,token='normal',analysis=False,multipv=1)
        pool.submit(preset.engine,own);r=wait(pool,own.token)
        assert not r['cached'] and 'candidates' not in r
        repeat=replace(own,token='normal-repeat');pool.submit(preset.engine,repeat)
        assert wait(pool,repeat.token)['cached']
        print('PASS: real MultiPV candidates, normal moves, and independent bounded caches',flush=True)
        s={'prefs':{'elo':1500,'autoPremove':True,'enabled':True,'side':'auto',
                    'premoveBreadth':5,'premovePolicy':'balanced'},
           'phase':'playing','atEnd':True,'side':'black','turn':'white','reason':'opponent',
           'gameId':'real','revision':0,'fen':chess.STARTING_FEN,'history':[],'rootFen':''}
        planner=Premove();started=time.monotonic();planner.update(s,pool,preset)
        requests=[]
        end=started+30
        while time.monotonic()<end:
            for r in pool.drain():
                if r['request'].owner==planner.owner:
                    requests.append(r['request'])
                    planner.accept(r,pool)
            planner.update(s,pool,preset)
            if planner.status in ('ready','withheld','error'):break
            time.sleep(.01)
        assert planner.status=='ready',planner.public_state()
        assert len(planner.branches)>=3 and len(planner.plan)==1
        assert all(r.nodes==preset.nodes for r in requests if not r.analysis)
        assert all(chess.Move.from_uci(m) in chess.Board(fen).legal_moves for fen,m in planner.ready.items())
        print(f'PASS: real branch planner ready in {time.monotonic()-started:.2f}s; {len(planner.branches)} branches, one queue item; reply preset preserved',flush=True)
    finally:
        pool.close()


if __name__=='__main__':main()
