"""One renewable native premove, backed by several opponent branches."""
from collections import Counter, deque
import time
import uuid
import chess
from engine_runtime import Request, reconstruct_board

VALUES = {1:100,2:320,3:330,4:500,5:900,6:20000}


def captured_value(board, move):
    if board.is_en_passant(move):
        return 100
    piece = board.piece_at(move.to_square)
    return VALUES[piece.piece_type] if piece else 0


def exchange_gain(board, square, depth=3):
    """Bounded legal recaptures on one square, not a full evaluation."""
    if not depth:
        return 0
    best = 0
    for move in list(board.generate_legal_captures(to_mask=chess.BB_SQUARES[square])):
        gain = captured_value(board, move)+(VALUES[move.promotion]-100 if move.promotion else 0)
        board.push(move)
        gain -= exchange_gain(board, square, depth-1)
        board.pop()
        best = max(best, gain)
    return best


def reply_risk(board, move):
    """Immediate exchange loss, or None for draw and mate-in-one traps."""
    gain = captured_value(board, move)+(VALUES[move.promotion]-100 if move.promotion else 0)
    board.push(move)
    try:
        if board.is_stalemate() or board.is_repetition(3):
            return None
        if board.is_checkmate():
            return 0
        for counter in list(board.legal_moves):
            if board.gives_check(counter):
                board.push(counter)
                mate = board.is_checkmate()
                board.pop()
                if mate:
                    return None
        return max(0, exchange_gain(board, move.to_square)-gain)
    finally:
        board.pop()


class Premove:
    def __init__(self):
        self.owner = 'premove-'+uuid.uuid4().hex
        self.reset()

    def reset(self):
        self.context = None
        self.base = None
        self.pending = None
        self.ready = {}
        self.plan = []
        self.branches = []
        self.work = deque()
        self.screen = None
        self.status = 'idle'
        self.message = ''
        self.coverage = {}
        self.failed = False
        self.endgame = False
        self.advanced = True

    @staticmethod
    def context_for(s):
        return (s['gameId'],s['prefs']['elo'],s['revision'],s['side'])

    def update(self, s, pool, preset):
        enabled = bool(s and s['prefs'].get('autoPremove') and s['prefs']['enabled']
                       and s['phase']=='playing' and s['atEnd'] and s.get('side')
                       and s['prefs']['side']!='both' and s['reason'] in ('ready','opponent'))
        context = self.context_for(s) if enabled else None
        if not enabled or context!=self.context:
            pool.cancel(self.owner)
            self.reset()
            self.context = context
        if not enabled:
            return None
        fen = chess.Board(s['fen']).fen()
        if s['turn']==s['side']:
            pool.cancel(self.owner)
            self.pending = None
            self.work.clear()
            self.screen = None
            self.plan = []
            return self.ready.get(fen)
        if self.base==fen:
            self._screen_slice()
            return None
        pool.cancel(self.owner)
        self.base = fen
        self.ready = {}
        self.plan = []
        self.branches = []
        self.work.clear()
        self.screen = None
        self.coverage = {}
        self.failed = False
        self.status,self.message = 'predicting','Membaca cabang lawan'
        self.model,self.nodes = preset.engine,preset.nodes
        self.width = min(8,max(1,int(s['prefs'].get('premoveBreadth',5))))
        self.advanced = bool(s['prefs'].get('advancedPremove', True))
        self.policy = s['prefs'].get('premovePolicy','balanced')
        if self.policy not in ('strict','balanced','active'):
            self.policy = 'balanced'
        self.root = reconstruct_board(Request(self.owner,'root',s['gameId'],s['fen'],
                                   s['prefs']['elo'],s.get('rootFen',''),tuple(s.get('history',()))))
        self.endgame = bool(s['prefs'].get('endgamePremove', True)) and self._is_endgame(self.root)
        if self.endgame:
            self.width = max(self.width, 8)
        if self.root.is_game_over(claim_draw=True):
            self.status = 'terminal'
            return None
        legal = list(self.root.legal_moves)
        req = Request(self.owner,uuid.uuid4().hex,s['gameId'],s['fen'],s['prefs']['elo'],
                      s.get('rootFen',''),tuple(s.get('history',())),
                      min(256,max(48,self.nodes*8,self.width*8)),True,self.width)
        self.pending = (req.token,'predict',None)
        if len(legal)==1:
            self.accept({'request':req,'move':legal[0].uci()},pool)
        else:
            pool.submit(self.model,req)
        return None

    @staticmethod
    def _is_endgame(board):
        """Recognize a practical endgame without trying to classify every tablebase position."""
        pieces=[p for p in board.piece_map().values() if p.piece_type not in (chess.KING,chess.PAWN)]
        queens=any(p.piece_type==chess.QUEEN for p in board.piece_map().values())
        return not queens and len(pieces)<=4 and board.fullmove_number>=12

    def _next_reply(self, pool):
        if not self.work:
            self._begin_screen()
            return
        index,req = self.work.popleft()
        self.pending = (req.token,'reply',index)
        pool.submit(self.model,req)

    def accept(self, result, pool):
        req = result['request']
        if not self.pending or req.token!=self.pending[0]:
            return
        _,stage,index = self.pending
        self.pending = None
        if result.get('error') or not result.get('move'):
            if stage=='reply':
                self._next_reply(pool)
            else:
                self.failed = True
                self.status,self.message = 'error','Prediksi belum siap'
            return
        try:
            board = reconstruct_board(req)
            if stage=='predict':
                seeds = result.get('candidates') or [{'move':result['move'],'score_cp':None}]
                seen = set()
                for seed in seeds[:self.width]:
                    move = chess.Move.from_uci(seed['move'])
                    if move in seen or move not in board.legal_moves:
                        continue
                    seen.add(move)
                    branch = board.copy()
                    san = branch.san(move)
                    branch.push(move)
                    if branch.is_game_over(claim_draw=True):
                        continue
                    index = len(self.branches)
                    self.branches.append({'opponent':move.uci(),'before':branch.fen(en_passant='fen'),
                                          'reply':None,'score_cp':seed.get('score_cp')})
                    reply = Request(self.owner,uuid.uuid4().hex,req.game,branch.fen(),req.elo,
                                    req.root_fen if req.history else req.fen,req.history+(san,),self.nodes)
                    self.work.append((index,reply))
                self.status,self.message = 'replies','Menyiapkan respons tiap cabang'
                self._next_reply(pool)
            else:
                move = chess.Move.from_uci(result['move'])
                if move in board.legal_moves:
                    self.branches[index]['reply'] = move.uci()
                    self.ready[board.fen()] = move.uci()
                self._next_reply(pool)
        except (ValueError,KeyError,TypeError):
            if stage=='reply':
                self._next_reply(pool)
            else:
                self.failed,self.status = True,'error'

    def _begin_screen(self):
        votes = Counter()
        for rank,branch in enumerate(self.branches):
            if branch['reply']:
                votes[branch['reply']] += 1/(rank+1)
        if not votes:
            self.status,self.message = 'withheld','Tidak ada respons siap'
            return
        legal=list(self.root.legal_moves)
        positions=[]
        for move in legal:
            board=self.root.copy();board.push(move);positions.append(board)
        # Prefer replies usable after many opponent choices, rather than a narrow
        # capture which only works if the very first prediction happens to match.
        coverage={move:sum(board.is_legal(chess.Move.from_uci(move)) for board in positions) for move in votes}
        high=max(votes.values())
        forcing={m:0 for m in votes}
        for board in positions:
            for move in forcing:
                candidate=chess.Move.from_uci(move)
                if candidate in board.legal_moves and (board.is_capture(candidate) or board.gives_check(candidate)):
                    forcing[move]+=1
        ranked=sorted(votes,key=lambda m:(2*coverage[m]/len(legal)+votes[m]/high,
                                           forcing[m]/max(1,len(legal)) if self.advanced else 0,
                                           votes[m]),reverse=True)
        self.screen = {'candidates':deque(ranked),
                       'legal':legal,'move':None,'index':0,'responses':[]}
        self.status,self.message = 'screening','Memeriksa respons di cabang lain'

    def _screen_slice(self):
        """Cooperative slices keep the browser loop responsive during branch checks."""
        if not self.screen:
            return
        end = time.monotonic()+.012
        screen = self.screen
        cap = {'strict':0,'balanced':100,'active':220}[self.policy]
        while self.screen and time.monotonic()<end:
            if screen['move'] is None:
                if not screen['candidates']:
                    self.status,self.message = 'withheld','Premove ditahan · variasi berisiko'
                    self.screen = None
                    return
                screen.update(move=screen['candidates'].popleft(),index=0,responses=[])
            if screen['index']>=len(screen['legal']):
                responses = screen['responses']
                if responses:
                    self.plan = [{**responses[0],'move':screen['move'],
                                  'states':[fen for r in responses for fen in (r['before'],r['after'])]}]
                    self.coverage = {'compatible':len(responses),'total':len(screen['legal']),
                                     'sampled':len(self.branches),'policy':self.policy}
                    self.status,self.message = 'ready','Satu premove siap · isi ulang tiap giliran'
                    self.screen = None
                    return
                screen['move'] = None
                continue
            opponent = screen['legal'][screen['index']]
            screen['index'] += 1
            board = self.root.copy()
            board.push(opponent)
            move = chess.Move.from_uci(screen['move'])
            if move not in board.legal_moves or board.is_game_over():
                continue  # The native site cancels a reply that is no longer legal.
            before = board.fen(en_passant='fen')
            risk = reply_risk(board,move)
            if risk is None or risk>cap:
                screen['move'] = None
                continue
            if self.endgame:
                # Endgames are especially vulnerable to accidental stalemate and
                # king exposure; require a legal continuation after the premove.
                board.push(move)
                safe_continuation=bool(list(board.legal_moves)) or board.is_checkmate()
                board.pop()
                if not safe_continuation:
                    screen['move'] = None
                    continue
            board.push(move)
            screen['responses'].append({'opponent':opponent.uci(),'before':before,
                                         'after':board.fen(en_passant='fen')})

    def public_state(self):
        return {'base':self.base,'status':self.status,'message':self.message,'endgame':self.endgame,
                'branches':[{'opponent':b['opponent'],'reply':b['reply']} for b in self.branches],
                'move':self.plan[0]['move'] if self.plan else None,'coverage':self.coverage}
