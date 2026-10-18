#!/usr/bin/env python3
"""Publish the completed low-level calibration and disable uncalibrated highs."""
from datetime import datetime, timezone
import json
from pathlib import Path
from summarize_ratings import summarize
from calibrate_v7_targeted import FOLDER, PROFILES, ROOT
from validate_v7_low import OUT, LOW_PROFILES, HOLDOUT

def main():
    old=json.loads((ROOT/'calibration-profiles.json').read_text())
    active={}
    lines=['# V7 — kalibrasi node utama single-PV 1500–2000','',
      '**288 game kalibrasi + 72 game holdout = 360 game untuk preset aktif.**','',
      'Langkah utama memakai Lc0 single-PV pada node aktual yang dicatat. Stockfish tidak memakai MultiPV. '
      'Profil 2100–2300 dinonaktifkan sampai ada kalibrasi terpisah.','',
      '| Tombol | Model | Node | Estimasi gabungan | Interval 95% | Kalibrasi W–D–L | Holdout W–D–L |','|---:|---|---:|---:|---:|---:|---:|']
    for profile in LOW_PROFILES:
        target,model,nodes=PROFILES[profile]
        crows=[json.loads(x) for x in (FOLDER/(profile+'.jsonl')).read_text().splitlines() if x.strip()]
        hrows=[json.loads(x) for x in (OUT/(profile+'.jsonl')).read_text().splitlines() if x.strip()]
        assert len(crows)==48 and len(hrows)==12
        c=summarize(crows); h=summarize(hrows)
        pooled=summarize(crows+[{**r,'opening':r['opening']+100} for r in hrows])
        active[str(target)]={'profile':profile,'engine':model,'nodes':nodes,'enabled':True,
          'estimate':pooled['local_reference_performance'],'interval':pooled['bootstrap_95_interval'],'games':60,
          'calibration_estimate':c['local_reference_performance'],
          'validation':{'games':12,'wins':h['wins'],'draws':h['draws'],'losses':h['losses'],
                        'estimate':h['local_reference_performance'],'interval':h['bootstrap_95_interval']},
          'target_delta':pooled['local_reference_performance']-target,
          'target_within_sampling_interval':pooled['bootstrap_95_interval'][0]<=target<=pooled['bootstrap_95_interval'][1]}
        lines.append(f"| {target} | {model} | {nodes} | {active[str(target)]['estimate']} | {active[str(target)]['interval'][0]}–{active[str(target)]['interval'][1]} | {c['wins']}–{c['draws']}–{c['losses']} | {h['wins']}–{h['draws']}–{h['losses']} |")
    presets={}
    for target in sorted(old['presets'],key=int):
        if target in active: presets[target]=active[target]
        else:
            legacy=dict(old['presets'][target]); legacy.update(enabled=False, legacy=True, status='uncalibrated-after-node-change')
            presets[target]=legacy
    document={'version':7,'created_utc':datetime.now(timezone.utc).isoformat(),
      'source':'calibration-v7-targeted-low','calibration_games':288,'holdout_games':72,
      'total_games':360,'node_multiplier':1,'mode':'single-pv',
      'active_targets':[1500,1600,1700,1800,1900,2000],
      'inactive_targets':[2100,2200,2300],
      'kind':'Local SF UCI_Elo-reference estimates; not Chess.com/FIDE ratings',
      'selection':'Only completed 1500–2000 targeted profiles were published. 2100–2300 remain disabled and were not recalibrated.',
      'presets':presets}
    (ROOT/'calibration-profiles.json').write_text(json.dumps(document,indent=2)+'\n')
    (FOLDER/'public-results-low.json').write_text(json.dumps({'created_utc':document['created_utc'],'calibration_games':288,'holdout_games':72,'total_verified_games':360,'presets':active},indent=2)+'\n')
    lines += ['', 'Interval menunjukkan variasi sampel dan bukan sertifikasi Elo Chess.com/FIDE.']
    (FOLDER/'REPORT-low.md').write_text('\n'.join(lines)+'\n')
    print('PUBLISHED LOW PROFILES: 1500-2000; 2100-2300 disabled',flush=True)

if __name__=='__main__': main()
