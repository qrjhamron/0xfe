"""Guarded, opt-in board input; one nonblocking cursor step per daemon poll."""
import math
import time
import chess

from human_style import cursor_bow, jitter_factor, tempo_multiplier, valid_persona

GEOMETRY = """() => {
 const b=document.querySelector('wc-chess-board,chess-board');
 let r=b?.getBoundingClientRect();
 if(!r||r.width<80||r.height<80||document.hidden)return null;
 if(r.top<0||r.left<0||r.bottom>innerHeight||r.right>innerWidth){
   b.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});
   r=b.getBoundingClientRect();
 }
 return {x:r.x,y:r.y,w:r.width,h:r.height,flipped:!!b.game?.getOptions?.().flipped};
}"""
CURSOR = """p=>{
 let e=document.querySelector('#coach-mouse');
 if(!e){e=document.createElement('div');e.id='coach-mouse';
 e.textContent='➤';e.style.cssText='position:fixed;pointer-events:none;z-index:2147483647;color:#ffcb66;font-size:25px;text-shadow:0 1px 3px #000;transform:rotate(-35deg)';document.body.append(e);}
 e.style.left=p.x+'px';e.style.top=p.y+'px';
}"""

_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def material_edge(board):
    """Material balance from the side-to-move point of view, in pawns."""
    score = 0
    for piece in board.piece_map().values():
        value = _VALUES.get(piece.piece_type, 0)
        score += value if piece.color == board.turn else -value
    return score


class AutoMoves:
    def __init__(self):
        self.job = None
        self.attempted = None
        self.last_delay = None

    def cancel(self, page):
        self.job = None
        self.last_delay = None
        page.evaluate("()=>document.querySelector('#coach-mouse')?.remove()")

    @staticmethod
    def allowed(s):
        return bool(s and s.get('eligible') and s.get('phase') == 'playing'
                    and s.get('atEnd') and s.get('side') == s.get('turn')
                    and s.get('prefs', {}).get('side') != 'both')

    @staticmethod
    def rendered_source(rendered, move, token):
        """Source of the rendered recommendation behind this move, if it matches."""
        if (rendered or {}).get('token') == token and (rendered or {}).get('move') == move:
            return (rendered or {}).get('source')
        return None

    @staticmethod
    def apply_theory_tempo(delay, reason, source):
        """Memorized theory is played almost instantly; fixed delays stay manual."""
        if source == 'opening-book' and reason != 'fixed':
            reason = 'hafal teori' if reason == 'normal' else f'{reason} · hafal teori'
            return delay * 0.5, reason
        return delay, reason

    @staticmethod
    def adaptive_delay(s, board):
        prefs=s.get('prefs', {})
        base=max(0.0, min(10.0, float(prefs.get('delay', 300))/1000.0))
        if not prefs.get('adaptiveDelay', True) and not prefs.get('timeManagement', True):
            return base, 'fixed'
        factor=1.0; reasons=[]
        clocks=s.get('clocks') or {}
        remaining=clocks.get(s.get('turn'))
        if prefs.get('timeManagement', True) and isinstance(remaining,(int,float)):
            if remaining < 3000: factor*=.12; reasons.append('waktu sangat kritis')
            elif remaining < 8000: factor*=.25; reasons.append('kritik waktu')
            elif remaining < 20000: factor*=.4; reasons.append('waktu menipis')
            elif remaining < 60000: factor*=.65; reasons.append('waktu rendah')
            elif remaining < 120000: factor*=.85
        if prefs.get('adaptiveDelay', True):
            legal=list(board.legal_moves); captures=sum(board.is_capture(m) for m in legal)
            check=board.is_check(); complexity=min(1.45,1.0 + max(0,len(legal)-24)*.008 + captures*.018 + (0.18 if check else 0))
            factor*=complexity
            if complexity>1.12: reasons.append('posisi taktis')
            if len(legal)==1:
                # Humans play forced replies almost instantly.
                factor*=.5; reasons.append('langkah paksa')
            edge=material_edge(board)
            if edge>=4:
                # Clearly winning players relax and move fast.
                factor*=.85; reasons.append('unggul materi')
            elif edge<=-4:
                # Clearly losing players double-check and slow down.
                factor*=1.15; reasons.append('bertahan')
        # Persona tempo fingerprint: one base tempo per player plus natural
        # variation per persona+position, so the same person waits the same
        # time on the same position in every game. Snapshots without a
        # persona keep their exact legacy timing.
        persona=prefs.get('persona')
        if valid_persona(persona):
            factor*=tempo_multiplier(persona)
            factor*=jitter_factor(persona,board.fen())
        return max(0.0,min(10.0,base*factor)), ', '.join(reasons) or 'normal'

    def tick(self, page, s, rendered):
        queued = s.get('queuedMove') if s else None
        armed = bool(s and (s['prefs'].get('autoMove') or s['prefs'].get('autoPremove') or queued))
        if not armed or not self.allowed(s) or bool(s.get('native',{}).get('queue')):
            if self.job:
                self.cancel(page)
            return
        move = queued or ((rendered or {}).get('move') if (rendered or {}).get('token') == s['token'] else None)
        if not move:
            return
        key = (s['token'], move)
        if self.job and self.job['key'] != key:
            self.cancel(page)
        if self.attempted == s['token']:
            return
        if not self.job:
            board = chess.Board(s['fen'])
            try:
                legal = chess.Move.from_uci(move) in board.legal_moves
            except ValueError:
                legal = False
            if not legal:
                self.attempted = s['token']
                page.evaluate("()=>window.__chessArrowCoach.automationResult('Premove batal: langkah tidak legal',true)")
                return
            geometry = page.evaluate(GEOMETRY)
            if not geometry:
                return
            delay, delay_reason = self.adaptive_delay(s, board)
            delay, delay_reason = self.apply_theory_tempo(
                delay, delay_reason, self.rendered_source(rendered, move, s['token']))
            self.job = dict(key=key, move=move, token=s['token'], geometry=geometry,
                            due=time.monotonic()+delay, step=0,
                            persona=s.get('prefs',{}).get('persona'),
                            duration=max(.06,min(.6,s['prefs'].get('cursorMs',120)/1000)))
            self.last_delay = (s['token'], round(delay*1000), delay_reason)
            page.evaluate("r=>window.__chessArrowCoach.automationResult('Menunggu delay · '+r)", delay_reason)
            return
        job = self.job
        if time.monotonic() < job['due']:
            return
        # Poll again immediately before mouse input, rather than trusting the caller's snapshot.
        current = page.evaluate('()=>window.__chessArrowCoach?.read()')
        geometry = page.evaluate(GEOMETRY)
        if not self.allowed(current) or current['token'] != job['token'] or geometry != job['geometry']:
            self.cancel(page)
            return
        step = job['step']
        def point(square):
            file = ord(square[0])-97
            rank = int(square[1])-1
            col, row = (7-file, rank) if geometry['flipped'] else (file, 7-rank)
            return (geometry['x']+(col+.5)*geometry['w']/8,
                    geometry['y']+(row+.5)*geometry['h']/8)
        start, end = point(move[:2]), point(move[2:4])
        if step < 6:
            # First segment approaches source; second segment travels to destination.
            # The travel eases in-out with a slight deterministic bow, like a hand
            # slowing into the square. Both clicks stay pixel-exact.
            if step < 2:
                x, y = start
            else:
                f = (step-1)/4
                eased = f*f*(3-2*f)
                x, y = (start[0]+(end[0]-start[0])*eased, start[1]+(end[1]-start[1])*eased)
                dx, dy = end[0]-start[0], end[1]-start[1]
                length = math.hypot(dx, dy)
                curve = cursor_bow(job.get('persona'), move[:2], move[2:4])
                if length > 1 and curve:
                    bow = math.sin(math.pi*f)*curve/length
                    x, y = (x-dy*bow, y+dx*bow)
            # Refuse clicks when a dialog or other element covers the board.
            visible = page.evaluate("p=>document.elementFromPoint(p.x,p.y)?.closest('wc-chess-board,chess-board')!=null", {'x': x, 'y': y})
            if not visible:
                self.cancel(page)
                return
            page.mouse.move(x, y)
            page.evaluate(CURSOR, {'x': x, 'y': y})
            if step in (1, 5):
                page.mouse.click(x, y)
            job['step'] += 1
            # Eased pacing with the same total duration and click count.
            job['due'] = time.monotonic()+job['duration']*(0.8,1.0,1.2,1.2,1.0,0.8)[step]/6
        else:
            if len(move)==5 and not job.get('promotion_done'):
                color='w' if chess.Board(s['fen']).turn else 'b'
                piece=move[4]
                names={'q':'queen','r':'rook','b':'bishop','n':'knight'}
                name=names[piece]
                target=page.locator(f'.promotion-piece.{color}{piece},.promotion-window .{color}{piece},.promotion-selector .{color}{piece},[data-piece="{color}{piece}"],[data-promotion="{piece}"],[aria-label*="{name}" i]')
                visible=next((target.nth(i) for i in range(target.count()) if target.nth(i).is_visible()),None)
                if visible is None:
                    # Some board builds expose only a promotion menu with no piece classes.
                    # Use its four visible options in the standard queen/rook/bishop/knight order.
                    menu=page.locator('.promotion-window:visible,.promotion-selector:visible,[role="dialog"]:visible')
                    opts=menu.locator('button,[role="button"],div').filter(has=page.locator('svg')) if menu.count() else None
                    if opts and opts.count()>=4:
                        order={'q':0,'r':1,'b':2,'n':3}; visible=opts.nth(order[piece])
                if visible is None:
                    job.setdefault('promotion_deadline',time.monotonic()+1.5)
                    if time.monotonic()<job['promotion_deadline']:
                        return
                    self.attempted=s['token']
                    self.cancel(page)
                    page.evaluate("()=>window.__chessArrowCoach.automationResult('Pemilih promosi tidak terdeteksi · otomatis dihentikan',true)")
                    page.evaluate("()=>document.querySelector('#human-engine-panel [data-action=stop]')?.click()")
                    return
                box=visible.bounding_box()
                x,y=box['x']+box['width']/2,box['y']+box['height']/2
                page.mouse.move(x,y)
                page.evaluate(CURSOR,{'x':x,'y':y})
                page.mouse.click(x,y)
                job['promotion_done']=True
            self.attempted = s['token']
            self.job = None
            page.evaluate("()=>{document.querySelector('#coach-mouse')?.remove();window.__chessArrowCoach?.automationResult('Input terkirim · menunggu papan',true)}")
