"""Checks for bounded MultiPV choice and the small opening book."""
import chess
from types import SimpleNamespace
from arrows import choose_candidate, multipv_for_elo
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
