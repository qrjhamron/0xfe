"""Branch/refill/stale-result checks, plus optional real-engine MultiPV integration."""
import time
from collections import deque
from types import SimpleNamespace
import chess
from premove import Premove, reply_risk
from engine_runtime import reconstruct_board


class Pool:
    def __init__(self):
        self.jobs = deque()
        self.cancels = []
    def cancel(self,owner):
        self.cancels.append(owner)
    def submit(self,engine,req):
        self.jobs.append(req)


S = {'prefs':{'elo':1500,'autoPremove':True,'enabled':True,'side':'auto',
              'premoveBreadth':5,'premovePolicy':'balanced'},
     'phase':'playing','atEnd':True,'side':'black','turn':'white','reason':'opponent',
     'gameId':'one','revision':0,'fen':chess.STARTING_FEN,'history':[],'rootFen':''}
PRESET = SimpleNamespace(engine='test',nodes=2)


def finish(planner,pool,s,replies):
    req = pool.jobs.popleft()
    assert req.analysis and req.multipv==5
    planner.accept({'request':req,'move':next(iter(replies)),
                    'candidates':[{'move':m,'score_cp':0} for m in replies]},pool)
    for opponent,own in replies.items():
        req = pool.jobs.popleft()
        assert not req.analysis and req.nodes==2
        assert reconstruct_board(req).peek().uci()==opponent
        planner.accept({'request':req,'move':own},pool)
    deadline = time.monotonic()+4
    while planner.screen and time.monotonic()<deadline:
        planner.update(s,pool,PRESET)
    assert not planner.screen


def main():
    pool = Pool();p = Premove();p.update(S,pool,PRESET)
    replies = {'e2e4':'e7e5','d2d4':'d7d5','g1f3':'g8f6','c2c4':'e7e5','g2g3':'e7e5'}
    finish(p,pool,S,replies)
    assert len(p.branches)==5 and len(p.ready)==5
    assert len(p.plan)==1 and p.plan[0]['move']=='e7e5'
    assert p.coverage['total']==20 and p.coverage['compatible']==20
    print('PASS: five engine branches; one robust premove; all 20 legal opponent moves screened')
    endgame_board=chess.Board('8/5pk1/6p1/7p/2P5/2K3P1/5P2/8 w - - 0 18')
    assert Premove._is_endgame(endgame_board)
    assert not Premove._is_endgame(chess.Board())
    print('PASS: endgame detector activates only on queenless low-material positions')
    board = chess.Board();board.push_uci('d2d4')
    assert p.update({**S,'fen':board.fen(),'turn':'black','reason':'ready'},pool,PRESET)=='d7d5'
    board = chess.Board();board.push_uci('h2h4')
    assert p.update({**S,'fen':board.fen(),'turn':'black','reason':'ready'},pool,PRESET) is None
    print('PASS: actual opponent branch selects its own cached response; unseen branch never reuses a guess')
    board = chess.Board();board.push_uci('e2e4');board.push_uci('e7e5')
    next_turn = {**S,'fen':board.fen(en_passant='fen'),'history':['e4','e5']}
    p.update(next_turn,pool,PRESET)
    finish(p,pool,next_turn,{'g1f3':'b8c6','b1c3':'b8c6','f1c4':'b8c6'})
    assert len(p.plan)==1 and p.plan[0]['move']=='b8c6' and len(p.ready)==3
    assert p.base==board.fen()
    print('PASS: new opponent turn refills one premove rather than stopping after the first round')
    opening=chess.Board();opening.push_uci('e2e4')
    white={**S,'side':'white','turn':'black','fen':opening.fen(),'history':['e4']}
    broad=Premove();branch_pool=Pool();broad.update(white,branch_pool,PRESET)
    finish(broad,branch_pool,white,{'d7d5':'e4d5','e7e5':'g1f3','c7c5':'g1f3'})
    assert broad.plan[0]['move']=='g1f3'
    print('PASS: broad reusable response outranks a capture tied to one opponent prediction')
    p.update({**S,'gameId':'next'},pool,PRESET);old=pool.jobs.popleft()
    p.update({**S,'prefs':{**S['prefs'],'autoPremove':False}},pool,PRESET)
    p.accept({'request':old,'move':'e2e4'},pool)
    assert not p.ready and not p.plan and not p.pending
    p.update(S,pool,PRESET);old=pool.jobs.popleft()
    p.update({**S,'revision':1},pool,PRESET)
    p.accept({'request':old,'move':'e2e4'},pool)
    assert not p.branches
    print('PASS: disable, revision changes, and stale completions cannot revive an old plan')
    forced = {**S,'side':'white','turn':'black','fen':'7k/8/5K2/7Q/8/8/8/7R b - - 0 1'}
    pool=Pool();p=Premove();p.update(forced,pool,PRESET)
    req=pool.jobs.popleft();assert not req.analysis
    p.accept({'request':req,'move':'h5h7'},pool)
    while p.screen:p.update(forced,pool,PRESET)
    assert len(p.plan)==1 and not pool.jobs
    print('PASS: forced opponent bypasses prediction search; no multi-step queue, even on a forced line')
    board=chess.Board('3rk3/8/8/8/8/8/8/3QK3 w - - 0 1')
    assert reply_risk(board,chess.Move.from_uci('d1d7'))>220
    board=chess.Board('k7/2Q5/2K5/8/8/8/8/8 w - - 0 1')
    assert reply_risk(board,chess.Move.from_uci('c7b6')) is None
    board=chess.Board();board.push_uci('f2f3');board.push_uci('e7e5')
    assert reply_risk(board,chess.Move.from_uci('g2g4')) is None
    print('PASS: hanging queen, immediate stalemate, and mate-in-one traps are withheld')
    print('ALL BRANCH PLANNER CHECKS PASSED')


if __name__=='__main__':main()
