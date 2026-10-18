#!/usr/bin/env python3
"""Publish the focused 1600/1700 recalibration."""
from datetime import datetime, timezone
import json
from pathlib import Path
from summarize_ratings import summarize

ROOT=Path(__file__).resolve().parent
ROOTCAL=ROOT/'calibration-profiles.json'
FOCUS=ROOT/'calibration-v7-focus'; HOLD=ROOT/'validation-v7-focus'
FOCUS_MAP={'1600':('p1600f','meangirl7',7),'1700':('p1700f','evilgyal6',4)}

def main():
    doc=json.loads(ROOTCAL.read_text())
    for target,(profile,model,nodes) in FOCUS_MAP.items():
        c=[json.loads(x) for x in (FOCUS/(profile+'.jsonl')).read_text().splitlines() if x.strip()]
        h=[json.loads(x) for x in (HOLD/(profile+'.jsonl')).read_text().splitlines() if x.strip()]
        pooled=summarize(c+[{**r,'opening':r['opening']+100} for r in h]); cs=summarize(c); hs=summarize(h)
        doc['presets'][target].update({'profile':profile,'engine':model,'nodes':nodes,'enabled':True,
          'estimate':pooled['local_reference_performance'],'interval':pooled['bootstrap_95_interval'],'games':60,
          'calibration_estimate':cs['local_reference_performance'],
          'validation':{'games':12,'wins':hs['wins'],'draws':hs['draws'],'losses':hs['losses'],
                        'estimate':hs['local_reference_performance'],'interval':hs['bootstrap_95_interval']},
          'target_delta':pooled['local_reference_performance']-int(target),
          'target_within_sampling_interval':pooled['bootstrap_95_interval'][0]<=int(target)<=pooled['bootstrap_95_interval'][1],
          'calibration_source':'calibration-v7-focus'})
    doc['source']='calibration-v7-targeted-low-focus';doc['created_utc']=datetime.now(timezone.utc).isoformat()
    doc['selection']='1500–2000 active; 1600 and 1700 use focused node candidates. 2100–2300 remain disabled.'
    ROOTCAL.write_text(json.dumps(doc,indent=2)+'\n')
    lines=['# V7 — target low-level 1500–2000','',
      '1500–2000 aktif; 2100–2300 dinonaktifkan. Estimasi adalah performa relatif terhadap Stockfish lokal, bukan Elo Chess.com/FIDE.','',
      '| Level | Estimasi | Interval 95% | Node |','|---:|---:|---:|---:|']
    for target in ('1500','1600','1700','1800','1900','2000'):
        p=doc['presets'][target];lines.append(f"| {target} | {p['estimate']} | {p['interval'][0]}–{p['interval'][1]} | {p['nodes']} |")
    (ROOT/'calibration-v7-targeted'/'REPORT-low.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'calibration-v7-targeted'/'public-results-low.json').write_text(json.dumps({'created_utc':doc['created_utc'],'presets':{k:doc['presets'][k] for k in ('1500','1600','1700','1800','1900','2000')}},indent=2)+'\n')
    print('PUBLISHED focused 1600/1700 profiles',flush=True)

if __name__=='__main__': main()
