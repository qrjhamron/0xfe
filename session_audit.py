"""Keep native events tied to their own game, independent of console logs."""
import hashlib
import json
import logging
from pathlib import Path


class SessionAudit:
    def __init__(self, folder):
        self.folder=Path(folder)
        self.game=None
        self.events={}
        self.tempo=[]
        self.signature=None

    def note_tempo(self, fen, delay_ms, reason):
        """Record one automation delay sample for cross-game tempo analysis."""
        self.tempo.append({'fen':fen,'delay_ms':delay_ms,'reason':reason})
        self.tempo=self.tempo[-128:]

    def sync(self, snapshot, audit, url):
        if not snapshot or not audit or audit.get('gameId')!=snapshot.get('gameId'):
            return
        game=audit['gameId']
        if game!=self.game:
            self.game,self.events,self.tempo,self.signature=game,{},[],None
        for event in audit.get('events',[]):
            if event.get('gameId')==game and isinstance(event.get('id'),int):
                self.events[event['id']]=event
        counts=audit.get('counts',{})
        signature=(json.dumps(counts,sort_keys=True),snapshot.get('fen'),snapshot.get('phase'),len(self.events),len(self.tempo))
        if signature==self.signature:
            return
        payload={'game_id':game,'url':url.split('?',1)[0],
                 'level':snapshot.get('prefs',{}).get('elo'),
                 'persona':snapshot.get('prefs',{}).get('persona'),
                 'opening_line':list(snapshot.get('history') or [])[:8],
                 'phase':snapshot.get('phase'),
                 'result':snapshot.get('result'),'last_fen':snapshot.get('fen'),
                 'counts':counts,'tempo':self.tempo,
                 'events':[self.events[k] for k in sorted(self.events)]}
        try:
            self.folder.mkdir(parents=True,exist_ok=True)
            name=hashlib.sha256(game.encode()).hexdigest()[:16]
            target=self.folder/(name+'.json')
            temp=target.with_suffix('.tmp')
            temp.write_text(json.dumps(payload,indent=2))
            temp.replace(target)
            self.signature=signature
        except OSError as exc:
            logging.warning('Native audit unavailable (%s)',type(exc).__name__)
