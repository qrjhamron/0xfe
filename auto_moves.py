"""Guarded, opt-in board input; one nonblocking cursor step per daemon poll."""
import time
import chess

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


class AutoMoves:
    def __init__(self):
        self.job = None
        self.attempted = None

    def cancel(self, page):
        self.job = None
        page.evaluate("()=>document.querySelector('#coach-mouse')?.remove()")

    @staticmethod
    def allowed(s):
        return bool(s and s.get('eligible') and s.get('phase') == 'playing'
                    and s.get('atEnd') and s.get('side') == s.get('turn')
                    and s.get('prefs', {}).get('side') != 'both')

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
            if remaining < 8000: factor*=.25; reasons.append('kritik waktu')
            elif remaining < 20000: factor*=.4; reasons.append('waktu menipis')
            elif remaining < 60000: factor*=.65; reasons.append('waktu rendah')
            elif remaining < 120000: factor*=.85
        if prefs.get('adaptiveDelay', True):
            legal=list(board.legal_moves); captures=sum(board.is_capture(m) for m in legal)
            check=board.is_check(); complexity=min(1.45,1.0 + max(0,len(legal)-24)*.008 + captures*.018 + (0.18 if check else 0))
            factor*=complexity
            if complexity>1.12: reasons.append('posisi taktis')
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
            self.job = dict(key=key, move=move, token=s['token'], geometry=geometry,
                            due=time.monotonic()+delay, step=0,
                            duration=max(.06,min(.6,s['prefs'].get('cursorMs',120)/1000)))
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
            if step < 2:
                x, y = start
            else:
                f = (step-1)/4
                x, y = (start[0]+(end[0]-start[0])*f, start[1]+(end[1]-start[1])*f)
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
            job['due'] = time.monotonic()+job['duration']/6
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
