"""Checkpoint the final candidate and use both CPU workers for its remainder."""
import io,json,os,signal,subprocess,sys,time
from pathlib import Path
import chess.pgn
ROOT=Path(__file__).resolve().parent;folder=ROOT/'calibration-v6';log=ROOT/'runtime/calibration-v6.log'
while True:
    if 'V6 CALIBRATION COMPLETE' in log.read_text():raise SystemExit('Already finished')
    paths=[folder/(p+'.jsonl') for p in ['p1500a','p1500b','p1600','p1700','p1800','p1900','p2000','p2100','p2200']]
    if all(p.exists() and len(p.read_text().splitlines())==48 for p in paths):break
    time.sleep(1)
# Only this known benchmark process and its own engine children are stopped.
parent=1706
try:
    children=[int(x) for x in subprocess.check_output(['ps','--ppid',str(parent),'-o','pid='],text=True).split()]
except subprocess.CalledProcessError:children=[]
for pid in [parent,*children]:
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
time.sleep(1)
path=folder/'p2300.jsonl';pgn=folder/'p2300.pgn'
backup=folder/'checkpoint-before-parallel';backup.mkdir(exist_ok=True)
for file in [path,pgn]:(backup/file.name).write_bytes(file.read_bytes())
rows=[]
for line in path.read_text().splitlines():
    try:rows.append(json.loads(line))
    except json.JSONDecodeError:break
source=io.StringIO(pgn.read_text());games=[]
for row in rows:
    game=chess.pgn.read_game(source)
    assert game and not game.errors and game.headers['Result']==row['result']
    assert int(game.headers['Round'])==row['opening']+1
    assert (game.headers['White']=='p2300')==row['white']
    games.append(str(game))
path.write_text(''.join(json.dumps(r)+'\n' for r in rows));pgn.write_text('\n\n'.join(games)+'\n\n')
note={'reason':'Other candidates complete; resume remaining final-candidate games on two CPU workers',
      'completed_games_kept':len(rows),'policy':'Keep all committed results; in-flight game not counted; no outcome-based selection',
      'engine_options_unchanged':True,'references_unchanged':True}
(folder/'parallel-resume.json').write_text(json.dumps(note,indent=2))
with log.open('a') as out:
    out.write('RESUME FINAL CANDIDATE WITH TWO WORKERS\n');out.flush()
    subprocess.run([sys.executable,str(ROOT/'calibrate_v6.py')],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
print('Parallel remainder complete',flush=True)
