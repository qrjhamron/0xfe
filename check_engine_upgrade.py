"""Checks for bounded MultiPV choice and the small opening book."""
import chess
from types import SimpleNamespace
from arrows import choose_candidate, engine_for_position, multipv_for_elo
from engine_runtime import Request
from opening_book import lookup

assert multipv_for_elo(1500)==2
assert multipv_for_elo(1800)==3
assert multipv_for_elo(2100)==5
assert multipv_for_elo(2300)==6
assert lookup(chess.Board(),(),True)=='e2e4'
b=chess.Board(); b.push_san('e4'); assert lookup(b,('e4',),True)=='e7e5'
req=Request('o','stable-token','g',chess.STARTING_FEN,1500)
result={'move':'e2e4','candidates':[{'move':'e2e4','score_cp':20},{'move':'d2d4','score_cp':-30},{'move':'g1f3','score_cp':-200}]}
move,source=choose_candidate(req,result)
assert move in {'e2e4','d2d4'} and source.startswith('hybrid-multipv')
print('PASS: opening book, Elo-bounded MultiPV, and human-like candidate selection')
specs={'maia3':SimpleNamespace(available=True)}
preset=SimpleNamespace(engine='badgyal8')
assert engine_for_position('hybrid',preset,SimpleNamespace(phase='middlegame'),chess.STARTING_FEN,specs)=='maia3'
assert engine_for_position('hybrid',preset,SimpleNamespace(phase='tactical'),chess.STARTING_FEN,specs)=='badgyal8'
assert engine_for_position('hybrid',preset,SimpleNamespace(phase='fixed'),'6k1/6R1/5ppp/8/8/8/5PPP/6K1 b - - 0 1',specs)=='badgyal8'
assert engine_for_position('maia3',preset,SimpleNamespace(phase='middlegame'),chess.STARTING_FEN,specs)=='maia3'
assert engine_for_position('calibrated',preset,SimpleNamespace(phase='middlegame'),chess.STARTING_FEN,specs)=='badgyal8'
assert engine_for_position('hybrid',preset,SimpleNamespace(phase='middlegame'),chess.STARTING_FEN,{'maia3':SimpleNamespace(available=False)})=='badgyal8'
print('PASS: hybrid mode routes quiet positions to Maia and checks to Lc0')
