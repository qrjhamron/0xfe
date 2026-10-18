"""Record the last calibration-only refinement, preserving all prior evidence."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parent
source=ROOT/'calibration-profiles.json'
old=json.loads(source.read_text());assert old['total_games']==684
# Decision is based on calibration, not this candidate's validation outcome.
summary=json.loads((ROOT/'calibration-v6/summary.json').read_text())
cal=summary['results']['p2100r']
assert cal['bootstrap_95_interval'][0]>2100
plan={'reason':'The original 6-node candidate has calibration estimate 2279 with interval 2139–2428, excluding target 2100.',
 'basis':'Calibration only. No previous validation outcome is used to choose the 5-node budget.',
 'new_profile':'p2100s','nodes':5,'calibration_games':48,'new_validation_games':12,
 'validation_policy':'Use a new six-opening set for the changed preset. Preserve the retired preset validation separately.'}
(ROOT/'calibration-v6/final-refinement-plan.json').write_text(json.dumps(plan,indent=2))
shutil.copy2(source,ROOT/'calibration-v6/selection-before-final-refinement.json')
retired=ROOT/'validation-retired-v6';retired.mkdir(exist_ok=True)
for suffix in ['jsonl','pgn']:
 original=ROOT/'validation-v6'/('2100.'+suffix);target=retired/original.name
 assert original.exists() and not target.exists()
 shutil.move(original,target)
(retired/'config.json').write_text(json.dumps({'preset':old['presets']['2100'],'reason':plan,
 'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in retired.iterdir() if p.suffix in {'.jsonl','.pgn'}}},indent=2))

p=ROOT/'calibrate_v6.py';s=p.read_text().replace(" 'p2300r':(2300,'badgyal8',10),", " 'p2300r':(2300,'badgyal8',10),\n 'p2100s':(2100,'badgyal8',5),")
s=s.replace('def finish_last_parallel(folder):','def finish_last_parallel(folder,profile=\'p2300\'):').replace("    profile='p2300';path=folder/(profile+'.jsonl');pgn=folder/(profile+'.pgn')", "    path=folder/(profile+'.jsonl');pgn=folder/(profile+'.pgn')")
p.write_text(s)
p=ROOT/'analyze_v6.py';s=p.read_text().replace('opening_board,run_profile','opening_board,run_profile,finish_last_parallel').replace("config['calibration_games']=576", "config['calibration_games']=624").replace("'additional_games':96", "'additional_games':144")
s=s.replace("    results={}\n", "    extra=FOLDER/'p2100s.jsonl'\n    if not extra.exists() or len(extra.read_text().splitlines())!=48:\n        finish_last_parallel(FOLDER,'p2100s')\n    config['final_refinement']=json.loads((FOLDER/'final-refinement-plan.json').read_text())\n    (FOLDER/'config.json').write_text(json.dumps(config,indent=2)+'\\n')\n    results={}\n",1)
s=s.replace("chosen[2100]='p2100r'", "chosen[2100]='p2100s'").replace("'calibration_games':576", "'calibration_games':624").replace('576 games audited','624 games audited')
p.write_text(s)
p=ROOT/'validate_v6.py';s=p.read_text();at="FOLDER=ROOT/'validation-v6'"
insert='''HOLDOUT_2100=[
 ('Berlin quiet','e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Be7'),
 ('Sicilian Taimanov','e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6'),
 ('Caro exchange','e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6'),
 ('Modern Benoni','d4 Nf6 c4 c5 d5 e6 Nc3 exd5 cxd5 d6'),
 ('Queens gambit accepted','d4 d5 c4 dxc4 Nf3 Nf6 e3 e6'),
 ('Reti advance','Nf3 d5 c4 d4 e3 Nc6 exd4 Nxd4'),
]
'''
s=s.replace(at,insert+at).replace('        for index,opening in enumerate(HOLDOUT):', "        cases=HOLDOUT_2100 if profile=='p2100s' else HOLDOUT\n        for index,opening in enumerate(cases):")
s=s.replace('    for _,line in HOLDOUT:', '    for _,line in HOLDOUT+HOLDOUT_2100:')
s=s.replace("'openings':HOLDOUT,", "'openings':HOLDOUT,'replacement_2100_openings':HOLDOUT_2100,")
p.write_text(s)
p=ROOT/'finalize_v6.py';s=p.read_text().replace('from validate_v6 import HOLDOUT','from validate_v6 import HOLDOUT,HOLDOUT_2100')
s=s.replace("                for san in HOLDOUT[row['opening']][1].split():opening.push_san(san)", "                cases=HOLDOUT_2100 if preset['profile']=='p2100s' else HOLDOUT\n                for san in cases[row['opening']][1].split():opening.push_san(san)")
s=s.replace('684','744').replace('576','624').replace('Dua belas kandidat','Tiga belas kandidat')
s=s.replace("document['holdout_games']=108", "document['holdout_games']=120;document['selected_preset_holdout_games']=108;document['retired_validation_games']=12")
s=s.replace("'holdout_games':108", "'holdout_games':120,'selected_preset_holdout_games':108,'retired_validation_games':12")
s=s.replace('624 game kalibrasi + 108 game validasi bukaan terpisah = 744 game yang diverifikasi.', '624 game kalibrasi + 108 game validasi preset terpilih + 12 game diagnostik yang diarsipkan = 744 game yang diverifikasi.')
s=s.replace('Tiga kandidat yang tidak terpilih tetap tersimpan', 'Empat kandidat yang tidak terpilih serta 12 game validasi dari kandidat 2100 yang diganti tetap tersimpan')
s=s.replace('624 calibration + 108 separate-opening validation games.', '624 calibration + 120 validation/diagnostic games.')
s=s.replace("for folder in [out,ROOT/'validation-v6']:", "for folder in [out,ROOT/'validation-v6',ROOT/'validation-retired-v6']:")
# Audit the retired validation too; no discarded losses or unexplained counts.
needle="    document['validated_utc']=datetime.now(timezone.utc).isoformat()"
insert='''    retired=ROOT/'validation-retired-v6'
    retired_rows=[json.loads(x) for x in (retired/'2100.jsonl').read_text().splitlines()]
    assert len(retired_rows)==12
    with (retired/'2100.pgn').open() as f:
        for row in retired_rows:
            game=chess.pgn.read_game(f);assert game and not game.errors
            board=game.board()
            for move in game.mainline_moves():
                assert move in board.legal_moves;board.push(move)
            outcome=board.outcome(claim_draw=True)
            assert game.headers['Result']==row['result']
            if row['termination']!='ply-cap':
                assert outcome and outcome.result()==row['result']
                assert row['score']==(.5 if outcome.winner is None else int(outcome.winner==row['white']))
        assert chess.pgn.read_game(f) is None
    print('AUDITED 12 RETIRED DIAGNOSTIC GAMES',flush=True)
'''
s=s.replace(needle,insert+needle)
s=s.replace("    lines+=['','## Pemeriksaan label','']", "    lines+=['','Kandidat 2100 diganti karena estimasi kalibrasinya terlalu tinggi. Validasi lamanya disimpan sebagai 12 game diagnostik, tanpa dipakai memilih batas pencarian baru. Validasi preset 2100 terakhir memakai enam bukaan baru yang berbeda lagi.','', '## Pemeriksaan label','']")
p.write_text(s)
p=ROOT/'presets.py';p.write_text(p.read_text().replace('!=684','!=744'))
p=ROOT/'README.md';s=p.read_text().replace('576','624').replace('dua belas kandidat','tiga belas kandidat').replace('Tiga kandidat tambahan tidak dipakai tetapi datanya tetap disimpan.', 'Empat kandidat tambahan tidak dipakai tetapi datanya tetap disimpan. Dua belas game diagnostik dari kandidat 2100 yang diganti juga diarsipkan, sehingga total yang diverifikasi 744 game.')
s=s.replace('Dua kandidat perantara ditambahkan', 'Tiga kandidat perantara ditambahkan')
p.write_text(s)
print('Recorded calibration-only refinement and retained prior validation',flush=True)
