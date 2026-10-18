"""Deterministic checks for clock-aware adaptive delay decisions."""
import chess
from auto_moves import AutoMoves

board=chess.Board()
base={'prefs':{'delay':1200,'timeManagement':True,'adaptiveDelay':True},'turn':'white','clocks':{'white':180000,'black':180000}}
normal,reason=AutoMoves.adaptive_delay(base,board)
low={**base,'clocks':{'white':6000,'black':180000}}
urgent,urgent_reason=AutoMoves.adaptive_delay(low,board)
assert urgent < normal and 'kritik waktu' in urgent_reason
fixed={**low,'prefs':{**base['prefs'],'timeManagement':False,'adaptiveDelay':False}}
fixed_delay,fixed_reason=AutoMoves.adaptive_delay(fixed,board)
assert abs(fixed_delay-1.2)<1e-9 and fixed_reason=='fixed'
tactical={**base,'clocks':{'white':180000,'black':180000}}
tactical_board=chess.Board('r3k2r/pppq1ppp/2npbn2/8/2B1P3/2N2N2/PPPQ1PPP/R3K2R w KQkq - 0 1')
tactical_delay,_=AutoMoves.adaptive_delay(tactical,tactical_board)
assert tactical_delay >= normal
print('PASS: normal/urgent/fixed/tactical time-management delay paths')
