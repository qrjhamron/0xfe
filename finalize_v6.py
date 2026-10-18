#!/usr/bin/env python3
"""Audit independent validation; publish honest local-reference calibration."""
from datetime import datetime,timezone
import json
from pathlib import Path
import zipfile
import chess
import chess.pgn
from calibrate_v6 import ROOT
from validate_v6 import HOLDOUT,HOLDOUT_2100
from summarize_ratings import summarize


def main():
    document=json.loads((ROOT/'calibration-profiles.json').read_text())
    summary=json.loads((ROOT/'calibration-v6/summary.json').read_text())
    assert document.get('calibration_games')==624, 'Calibration phase incomplete'
    assert len(summary['results'])==13 and sum(r['games'] for r in summary['results'].values())==624
    assert sum(len((ROOT/'calibration-v6'/(key+'.jsonl')).read_text().splitlines()) for key in summary['results'])==624
    assert set(document['presets'])=={str(n) for n in range(1500,2301,100)}
    public={};all_holdout=[]
    for target,preset in document['presets'].items():
        folder=ROOT/'validation-v6';rows=[json.loads(x) for x in (folder/(target+'.jsonl')).read_text().splitlines()]
        assert len(rows)==12 and len({(r['opening'],r['white']) for r in rows})==12
        with (folder/(target+'.pgn')).open() as f:
            for row in rows:
                game=chess.pgn.read_game(f);assert game and not game.errors
                assert game.headers['Profile']==preset['profile']
                assert int(game.headers['NodeBudget'])==preset['nodes']==row['nodes']
                assert int(game.headers['ReferenceElo'])==row['reference_elo']
                board=game.board();opening=chess.Board()
                cases=HOLDOUT_2100 if preset['profile']=='p2100s' else HOLDOUT
                for san in cases[row['opening']][1].split():opening.push_san(san)
                for move in game.mainline_moves():
                    assert move in board.legal_moves;board.push(move)
                    if board.ply()==row['opening_plies']:assert board.fen()==opening.fen()
                assert board.ply()==row['plies']
                outcome=board.outcome(claim_draw=True)
                if row['termination']!='ply-cap':
                    assert outcome and outcome.result()==row['result']==game.headers['Result']
                    assert row['score']==(.5 if outcome.winner is None else int(outcome.winner==row['white']))
            assert chess.pgn.read_game(f) is None
        holdout=summarize(rows)
        calibration=[json.loads(x) for x in (ROOT/'calibration-v6'/(preset['profile']+'.jsonl')).read_text().splitlines()]
        pooled=summarize(calibration+[{**r,'opening':r['opening']+100} for r in rows])
        preset.update(estimate=pooled['local_reference_performance'],interval=pooled['bootstrap_95_interval'],games=60,
                      calibration_estimate=summary['results'][preset['profile']]['local_reference_performance'],
                      validation={'games':12,'wins':holdout['wins'],'draws':holdout['draws'],'losses':holdout['losses'],
                                  'estimate':holdout['local_reference_performance'],'interval':holdout['bootstrap_95_interval']})
        preset['target_delta']=preset['estimate']-int(target)
        preset['target_within_sampling_interval']=preset['interval'][0]<=int(target)<=preset['interval'][1]
        public[target]={'estimate':preset['estimate'],'interval':preset['interval'],'games':60,
             'calibration':{k:summary['results'][preset['profile']][k] for k in ['wins','draws','losses','points','local_reference_performance','bootstrap_95_interval','search_stats']},
             'validation':preset['validation'],'combined':{k:pooled[k] for k in ['wins','draws','losses','points','administrative_draws']},
             'target_delta':preset['target_delta'],'target_within_sampling_interval':preset['target_within_sampling_interval']}
        all_holdout.extend(rows);print('AUDITED HOLDOUT',target,preset['estimate'],preset['interval'],flush=True)
    retired=ROOT/'validation-retired-v6'
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
    document['validated_utc']=datetime.now(timezone.utc).isoformat()
    document['total_games']=744;document['calibration_games']=624;document['holdout_games']=120;document['selected_preset_holdout_games']=108;document['retired_validation_games']=12
    document['note']='The fixed numeric buttons are nominal training targets. Estimates and intervals are local SF-reference measurements, not certified human ratings. Holdout did not alter profile selection.'
    target_file=ROOT/'calibration-profiles.json'
    temp=target_file.with_suffix('.tmp');temp.write_text(json.dumps(document,indent=2)+'\n');temp.replace(target_file)
    results={'created_utc':document['validated_utc'],'calibration_games':624,'holdout_games':120,'selected_preset_holdout_games':108,'retired_validation_games':12,'total_verified_games':744,'presets':public,
        'limitation':document['note']}
    out=ROOT/'calibration-v6';(out/'public-results.json').write_text(json.dumps(results,indent=2)+'\n')
    lines=['# V6 — kalibrasi level latihan 1500–2300','',
      '**624 game kalibrasi + 108 game validasi preset terpilih + 12 game diagnostik yang diarsipkan = 744 game yang diverifikasi.**','',
      'Angka tombol adalah target latihan tetap. Estimasi di bawah relatif terhadap setelan UCI_Elo Stockfish 19, '
      'bukan Elo Chess.com/FIDE yang terverifikasi. Interval 95% hanya mencerminkan variasi sampel; '
      'bias setelan lawan, waktu berpikir, perangkat, pemilihan kandidat dan bukaan tidak seluruhnya tercakup.','',
      '| Tombol | Estimasi lokal gabungan | Interval sampel 95% | Kalibrasi W–D–L (48) | Validasi W–D–L (12) |',
      '|---|---:|---:|---:|---:|']
    for target,row in public.items():
        c=row['calibration'];v=row['validation'];lo,hi=row['interval']
        lines.append(f'| {target} | {row["estimate"]} | {lo}–{hi} | {c["wins"]}–{c["draws"]}–{c["losses"]} | {v["wins"]}–{v["draws"]}–{v["losses"]} |')
    lines+=['','## Metode','',
      'Tiga belas kandidat masing-masing memainkan 48 game pada 24 bukaan dengan warna ditukar. '
      'Lawan acuan: 1320, 1700, 2100 dan 2500; masing-masing 12 game per kandidat. '
      'Dua kandidat dipertimbangkan untuk level 1500, lalu satu dipilih melalui aturan yang dicatat di konfigurasi. '
      'Dua kandidat untuk 1900/2000 diurutkan menurut estimasi hasil kalibrasi, bukan semata jumlah pencarian. Kandidat menengah lain ditentukan sebelumnya; dua kandidat perantara level tinggi dipilih dari hasil kalibrasi awal. Pilihan tiap preset dikunci sebelum validasi preset itu dijalankan. Refinemen level tinggi tidak memakai hasil validasi.','',
      'Sembilan preset terpilih menjalani 12 game tambahan pada enam bukaan berbeda, warna ditukar, '
      'melawan dua setelan acuan di sekitar targetnya. Tidak ada perubahan preset berdasarkan hasil validasi. '
      'Estimasi gabungan menggunakan 60 game per preset. Empat kandidat yang tidak terpilih serta 12 game validasi dari kandidat 2100 yang diganti tetap tersimpan '
      'sehingga total 744 game dapat diaudit. Ini validasi kecil, bukan pembuktian rating manusia.','',
      'Satu thread per engine, hash lawan 16 MiB, 50 ms per langkah untuk lawan, backend CPU lokal. '
      'Batas pencarian kandidat dicatat per game, dengan plafon waktu 2 detik. Prefetch dimatikan agar '
      'tidak memboroskan evaluasi di luar kebutuhan pencarian kecil. Pilihan langkah lawan acuan bersifat stokastik; pengulangan baru dapat memberi hasil berbeda. Jumlah node aktual dan latensi '
      'setiap langkah kandidat disimpan. Tidak ada injeksi kesalahan acak atau filter lawan yang '
      'menggantikan langkah model.','',
      'Skor menang=1, seri=0,5. Estimasi memakai rumus ekspektasi Elo logistik. Interval memakai '
      '5.000 bootstrap pasangan bukaan/warna, dikelompokkan menurut setelan lawan. '
      'Untuk estimasi gabungan, ID bukaan validasi dipisahkan dari bukaan kalibrasi. '
      'Tidak ada adjudikasi berdasarkan evaluasi. Klaim seri tiga kali posisi/50 langkah diterapkan; '
      'batas 300 ply menghasilkan seri administratif yang dilaporkan terpisah.','',
      'Interval antarlevel bisa tumpang tindih. Nilai yang berbeda 100 pada tombol tidak berarti '
      'perbedaan kekuatan 100 Elo telah terbukti. Label yang berada di luar interval hasilnya '
      'ditandai di bawah dan harus diperlakukan sebagai target nominal, bukan rating terukur.','',
      '## Pemeriksaan label','']
    for target,row in public.items():
        lines.append(f'- {target}: selisih estimasi terhadap target {row["target_delta"]:+d}; '
          f'target di dalam interval sampel: {"ya" if row["target_within_sampling_interval"] else "tidak"}; '
          f'seri administratif: {row["combined"]["administrative_draws"]}.')
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    for y,(target,row) in enumerate(public.items()):
        point=row['estimate'];lo,hi=row['interval']
        ax.errorbar(point,y,xerr=[[point-lo],[hi-point]],fmt='o',color='#14796b',capsize=4,
            label='Local estimate, 95% sampling interval' if y==0 else None)
        ax.scatter(int(target),y,color='#89919d',marker='x',s=45,label='Fixed training target' if y==0 else None)
    ax.set_yticks(range(9),list(public));ax.invert_yaxis();ax.set_ylabel('Fixed level button')
    ax.set_xlabel('Performance relative to local Stockfish UCI_Elo settings')
    ax.set_title('V6 calibration — 60 games per selected preset',loc='left',fontweight='bold')
    ax.grid(axis='x',alpha=.2);ax.legend(loc='lower right',fontsize=8)
    for side in ['top','right']:ax.spines[side].set_visible(False)
    fig.text(.01,-.025,'624 calibration + 120 validation/diagnostic games. Not Chess.com/FIDE Elo.',fontsize=9,color='#555')
    fig.savefig(out/'levels.png',dpi=180,bbox_inches='tight');plt.close(fig)
    with zipfile.ZipFile(ROOT.parent/'calibration-v6-results.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for folder in [out,ROOT/'validation-v6',ROOT/'validation-retired-v6']:
            for path in folder.iterdir():
                if path.suffix in {'.json','.jsonl','.pgn','.md','.png'}:archive.write(path,path.relative_to(ROOT))
        for name in ['calibrate_v6.py','analyze_v6.py','validate_v6.py','finalize_v6.py','calibration-profiles.json','rate_weights.py','summarize_ratings.py']:
            archive.write(ROOT/name,name)
    print('FINALIZED 744 VERIFIED GAMES',flush=True)

if __name__=='__main__':main()
