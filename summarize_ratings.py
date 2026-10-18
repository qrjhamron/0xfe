#!/usr/bin/env python3
"""Fit local performance rating with a stratified opening-pair bootstrap."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import json
import hashlib
import math
from pathlib import Path
import random
import zipfile
from lc0_config import WEIGHTS

ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'rating-results'


def expected(rating, opponent):
    return 1/(1+10**((opponent-rating)/400))


def fit_score(score,references):
    # The derivative of fractional-score logistic log likelihood is sum(score-p).
    if score<=0:return None
    if score>=len(references):return None
    lo,hi=-2000.,6000.
    for _ in range(65):
        mid=(lo+hi)/2
        if sum(expected(mid,r) for r in references)<score:lo=mid
        else:hi=mid
    return (lo+hi)/2


def quantile(values,q):
    values=sorted(values); x=(len(values)-1)*q;a=int(x);b=min(a+1,len(values)-1)
    return values[a]*(b-x)+values[b]*(x-a) if a!=b else values[a]


def summarize(rows,seed=20261017):
    references=[r['reference_elo'] for r in rows]
    scores=sum(r['score'] for r in rows)
    rating=fit_score(scores,references)
    groups=defaultdict(dict)
    for row in rows:
        groups[row['reference_elo']].setdefault(row['opening'],[]).append(row)
    if any(len(pair)!=2 or {r['white'] for r in pair}!={False,True}
           for openings in groups.values() for pair in openings.values()):
        raise ValueError('An opening/color pair is incomplete')
    rng=random.Random(seed)
    # For fixed reference counts, fitting only depends on total score.
    fits={half:fit_score(half/2,references) for half in range(1,2*len(rows))}
    bootstrap=[]
    for _ in range(5000):
        score=0
        for openings in groups.values():
            pair_scores=[sum(r['score'] for r in pair) for pair in openings.values()]
            score+=sum(rng.choice(pair_scores) for _ in pair_scores)
        value=fits.get(round(score*2))
        bootstrap.append(value if value is not None else (-2000 if score==0 else 6000))
    lower,upper=quantile(bootstrap,.025),quantile(bootstrap,.975)
    by_reference={}
    for opponent in sorted(groups):
        subset=[r for r in rows if r['reference_elo']==opponent]
        by_reference[str(opponent)]={'games':len(subset),'wins':sum(r['score']==1 for r in subset),
            'draws':sum(r['score']==.5 for r in subset),'losses':sum(r['score']==0 for r in subset),
            'score':sum(r['score'] for r in subset)}
    capped=[r for r in rows if r['termination']=='ply-cap']
    return {'games':len(rows),'wins':sum(r['score']==1 for r in rows),
        'draws':sum(r['score']==.5 for r in rows),'losses':sum(r['score']==0 for r in rows),
        'points':scores,'score_percent':round(100*scores/len(rows),2),
        'local_reference_performance':round(rating) if rating is not None else None,
        'bootstrap_95_interval':[round(lower),round(upper)],
        'bootstrap_method':'5000 resamples of color-swapped opening pairs, stratified by reference Elo',
        'outside_reference_span':rating is None or not min(references)<=rating<=max(references),
        'by_reference':by_reference,'termination_counts':dict(Counter(r['termination'] for r in rows)),
        'administrative_draws':len(capped),
        'cap_sensitivity_range':[fit_score(scores-.5*len(capped),references),
                                 fit_score(scores+.5*len(capped),references)] if capped else None,
        'mean_total_plies':round(sum(r['plies'] for r in rows)/len(rows),1),
        'total_game_seconds':round(sum(r['seconds'] for r in rows),1)}



def compare_paired(current, baseline, seed=20261017):
    """Resample matching opening/color pairs jointly between node budgets."""
    refs=[r['reference_elo'] for r in current]
    if sorted(refs)!=sorted(r['reference_elo'] for r in baseline):
        raise ValueError('Reference counts differ between runs')
    def grouped(rows):
        out=defaultdict(dict)
        for row in rows:
            key=(row['reference_elo'],row['opening'])
            out[key[0]][key[1]]=out[key[0]].get(key[1],0)+row['score']
        return out
    now,old=grouped(current),grouped(baseline)
    assert {ref:set(v) for ref,v in now.items()}=={ref:set(v) for ref,v in old.items()}
    fits={h:fit_score(h/2,refs) for h in range(1,2*len(refs))}
    def value(score):
        rating=fits.get(round(score*2))
        return rating if rating is not None else (-2000 if score==0 else 6000)
    rng=random.Random(seed);differences=[]
    for _ in range(5000):
        s0=s1=0
        for ref,pairs in now.items():
            ids=list(pairs)
            for _ in ids:
                index=rng.choice(ids);s0+=old[ref][index];s1+=now[ref][index]
        differences.append(value(s1)-value(s0))
    difference=value(sum(r['score'] for r in current))-value(sum(r['score'] for r in baseline))
    return {'difference':round(value(sum(r['score'] for r in current)))-round(value(sum(r['score'] for r in baseline))),'paired_bootstrap_95_interval':[
        round(quantile(differences,.025)),round(quantile(differences,.975))],
        'baseline_nodes':1,'method':'5000 joint stratified resamples of matching opening/color pairs'}


def main():
    global FOLDER
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,default=FOLDER)
    args=parser.parse_args()
    FOLDER=args.folder.resolve()
    config=json.loads((FOLDER/'config.json').read_text())
    nodes=config.get('nodes',1)
    games=2*config['opening_pairs_per_weight']
    result={}
    current_rows={}
    for key in WEIGHTS:
        rows=[json.loads(x) for x in (FOLDER/(key+'.jsonl')).read_text().splitlines()]
        if len(rows)!=2*config['opening_pairs_per_weight']:raise ValueError('Tournament incomplete: '+key)
        assert len({(r['opening'],r['white']) for r in rows})==len(rows)
        result[key]=summarize(rows)
        current_rows[key]=rows
    config['artifact_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [ROOT/'runtime/lc0', ROOT/'runtime/stockfish', *sorted((ROOT/'runtime/lc0-weights').glob('*.pb.gz'))]}
    baseline_path=ROOT/'rating-results/summary.json'
    baseline=None;comparison={}
    if nodes!=1 and baseline_path.exists():
        baseline=json.loads(baseline_path.read_text())
        for key in WEIGHTS:
            old_rows=[json.loads(line) for line in (baseline_path.parent/(key+'.jsonl')).read_text().splitlines()]
            comparison[key]=compare_paired(current_rows[key],old_rows)
    report={'created_utc' :datetime.now(timezone.utc).isoformat(),'config':config,'results':result,'comparison_to_node1':comparison}
    (FOLDER/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=[f'# Four Gyal weights: local {nodes}-node performance test','',
        '**This is performance against Stockfish 19 UCI_Elo settings, not verified Chess.com or FIDE Elo.**','',
        f'Each weight played {games} games: {games//2} hand-selected opening positions, each with colors swapped. '
        'There were 12 games per reference setting (1320, 1600, 1900, 2200). '
        f'Lc0 v0.32.1 used Eigen CPU, 1 thread, minibatch 1, nodes={nodes} and a 2 s search ceiling. '
        'Stockfish used 1 thread, 16 MiB hash, strength limiting, and 50 ms per move. '
        'Up to two games ran concurrently on a 2-core CPU quota. Neither engine used an external opening book or endgame tablebases.','',
        '| Weight | W–D–L | Points | Local performance | 95% sampling interval |',
        '|---|---:|---:|---:|---:|']
    for key,row in result.items():
        lo,hi=row['bootstrap_95_interval'];rating=row['local_reference_performance']
        lines.append(f'| {WEIGHTS[key][0]} | {row["wins"]}–{row["draws"]}–{row["losses"]} | '
            f'{row["points"]:g}/{games} | {rating} | {lo}–{hi} |')
    for key,row in result.items():
        if row['outside_reference_span']:
            lines+=['',f"**{WEIGHTS[key][0]}:** the fitted performance lies outside the tested reference range "
                f"({min(config['references'])}–{max(config['references'])}); this point estimate is an extrapolation."]
    if baseline:
        lines+=['','## Compared with 1 node','',
            '| Weight | 1-node estimate | Current estimate | Change | 95% sampling interval for change |',
            '|---|---:|---:|---:|---:|']
        for key in WEIGHTS:
            old=baseline['results'][key]['local_reference_performance'];now=result[key]['local_reference_performance']
            delta=comparison[key];lo,hi=delta['paired_bootstrap_95_interval']
            lines.append(f'| {WEIGHTS[key][0]} | {old} | {now} | {delta["difference"]:+d} | {lo:+d} to {hi:+d} |')
        lines+=['','Intervals for changes jointly resample matched opening/color pairs between runs. '
            'The Stockfish opponents choose moves stochastically and were limited by wall time; '
            'differences include run variability and are not an exact causal Elo gain.']
    lines+=['','## How to interpret the numbers','',
        'The performance is fitted with the standard logistic Elo expected-score formula '
        '`p = 1/(1 + 10**((reference - performance)/400))`, treating draws as half points. '
        'The interval uses 5,000 bootstrap resamples of opening/color pairs within each reference level. '
        'It reflects sampling variability only. It excludes systematic error from Stockfish calibration, '
        'very short thinking time, hardware, openings, and the draw protocol. '
        'A UCI_Elo setting is a requested strength, not an independent rating certificate; '
        'these results cannot establish a Chess.com/FIDE rating or that the four reference strengths '
        'are precisely separated as their labels imply. '
        'Overlapping intervals do not establish a reliable ordering. '
        'Higher node budgets need a new tournament.','',
        'Threefold repetition and 50-move draws were claimed when available. Games were played '
        'without evaluation-based win/loss adjudication. A 300-ply cap is an administrative draw '
        'and is counted separately below. Forced opening moves are included in PGNs; engines choose '
        'moves only after those lines. The fitted estimate applies to this test protocol, not to every position.','',
        '## Results by reference','',
        '| Weight | Reference | W–D–L | Points |','|---|---:|---:|---:|']
    for key,row in result.items():
        for ref,sub in row['by_reference'].items():
            lines.append(f'| {WEIGHTS[key][0]} | {ref} | {sub["wins"]}–{sub["draws"]}–{sub["losses"]} | {sub["score"]:g}/{sub["games"]} |')
    lines+=['','## Terminations','']
    for key,row in result.items():
        lines.append(f'- {WEIGHTS[key][0]}: '+', '.join(f'{k}: {v}' for k,v in row['termination_counts'].items()))
        if row['administrative_draws']:
            lines.append('  Sensitivity if every capped game is counted as a loss versus a win: '+str(row['cap_sensitivity_range']))
    lines+=['','## Reproduce','',
        f'From the project directory, run `.venv/bin/python rate_weights.py --nodes {nodes}` and then '
        f'`.venv/bin/python summarize_ratings.py --folder {FOLDER.name}`. Run `.venv/bin/python verify_rating_results.py --folder {FOLDER.name}` to audit every saved game. Existing JSONL files are resumed only with matching settings. '
        'Stockfish strength limiting has stochastic move selection, so fresh runs will vary. '
        'The ZIP contains source, configuration, per-game JSONL and full PGNs.']
    (FOLDER/'REPORT.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9,4.8),layout='constrained')
    keys=sorted(result,key=lambda k: result[k]['local_reference_performance'] or -10000)
    for y,key in enumerate(keys):
        row=result[key];point=row['local_reference_performance'];lo,hi=row['bootstrap_95_interval']
        if point is None:continue
        ax.errorbar(point,y,xerr=[[point-lo],[hi-point]],fmt='o',capsize=5,
                    color='#14796b',markersize=8,linewidth=2)
        ax.annotate(f'{point}  [{lo}, {hi}]',(hi,y),xytext=(12,0),textcoords='offset points',va='center',fontsize=10)
    ax.set_yticks(range(len(keys)),[WEIGHTS[key][0] for key in keys])
    ax.set_xlabel('Local performance relative to Stockfish UCI_Elo settings')
    ax.set_title(f'Gyal weights at {nodes} nodes — {games} games each',loc='left',fontweight='bold',pad=18)
    ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    ax.set_ylim(-.7,len(keys)-.3)
    points=[r['bootstrap_95_interval'][1] for r in result.values()]
    ax.set_xlim(min(r['bootstrap_95_interval'][0] for r in result.values())-70,max(points)+350)
    for side in ['top','right']:ax.spines[side].set_visible(False)
    fig.text(.01,-.035,'95% opening-pair bootstrap intervals. Stockfish: 50 ms/move. Not Chess.com/FIDE Elo.',fontsize=9,color='#555555')
    fig.savefig(FOLDER/'ratings.png',dpi=180,bbox_inches='tight')
    plt.close(fig)
    if baseline:
        fig,ax=plt.subplots(figsize=(9,4.8),layout='constrained')
        for y,key in enumerate(WEIGHTS):
            for offset,source,color,label in [(-.12,baseline['results'],'#929aa5','1 node'),
                                              (.12,result,'#14796b',f'{nodes} nodes')]:
                row=source[key];point=row['local_reference_performance'];lo,hi=row['bootstrap_95_interval']
                ax.errorbar(point,y+offset,xerr=[[point-lo],[hi-point]],fmt='o',capsize=4,
                    color=color,label=label if y==0 else None,linewidth=1.8)
        ax.set_yticks(range(len(WEIGHTS)),[v[0] for v in WEIGHTS.values()]);ax.invert_yaxis()
        ax.set_xlabel('Local performance relative to Stockfish UCI_Elo settings')
        ax.set_title(f'1 node vs {nodes} nodes — 48 games per weight per run',loc='left',fontweight='bold',pad=18)
        ax.legend(loc='lower right');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        for side in ['top','right']:ax.spines[side].set_visible(False)
        fig.text(.01,-.035,'95% opening-pair bootstrap intervals. Stockfish: 50 ms/move. Not Chess.com/FIDE Elo.',fontsize=9,color='#555555')
        fig.savefig(FOLDER/'comparison-node1.png',dpi=180,bbox_inches='tight');plt.close(fig)
    with zipfile.ZipFile(ROOT.parent/('gyal-rating-results.zip' if nodes==1 else f'gyal-rating-results-node{nodes}.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in FOLDER.iterdir():
            if path.suffix in {'.json','.jsonl','.pgn','.md','.png'}:archive.write(path,Path(FOLDER.name)/path.name)
        if baseline:
            for path in baseline_path.parent.iterdir():
                if path.suffix in {'.json','.jsonl','.pgn'}:
                    archive.write(path,Path('baseline-node1')/path.name)
        for name in ['rate_weights.py','summarize_ratings.py','verify_rating_results.py','lc0_config.py']:
            archive.write(ROOT/name,name)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
