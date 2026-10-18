#!/usr/bin/env python3
"""Lc0 resource/budget integration checks against real CPU models."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import chess
from check_engines import wait
from engine_runtime import EnginePool, Request, engine_specs
from setup_lc0 import download

ROOT = Path(__file__).resolve().parent

def main():
    specs = engine_specs(str(ROOT / 'runtime/stockfish'))
    pool = EnginePool(specs, threads=1, cache_size=4, idle_timeout=.8)
    report = {}
    try:
        for key, spec in specs.items():
            if spec.kind != 'nodes':
                continue
            assert spec.available, key
            job = Request(key, key+'-one', 'budgets', chess.STARTING_FEN, 1320)
            pool.submit(key, job); one = wait(pool, job.token)
            pid = pool.workers[key].engine.transport.get_pid()
            timings = {}
            for nodes in [16,64,256]:
                deeper = replace(job, token=f'{key}-{nodes}', nodes=nodes)
                pool.submit(key, deeper); result = wait(pool, deeper.token)
                assert not result['cached'], 'Different budgets must not share a move cache'
                timings[nodes] = result['latency_ms']
            assert pool.workers[key].engine.transport.get_pid() == pid
            repeat = replace(job, token=key+'-one-again')
            pool.submit(key, repeat); assert wait(pool, repeat.token)['cached']
            time.sleep(1)
            worker = pool.workers[key]
            assert worker.engine is None and worker.metrics['idle_unloads'] >= 1
            another = chess.Board();another.push_san('c4')
            wake = replace(job, token=key+'-wake', fen=another.fen())
            pool.submit(key,wake); wait(pool,wake.token)
            assert worker.engine.transport.get_pid() != pid
            for invalid in [0,257,1.5]:
                try:pool.submit(key,replace(job,nodes=invalid))
                except ValueError:pass
                else:raise AssertionError('Invalid node budget was accepted')
            report[key]={'nodes_latency_ms':timings,'idle_unloads':worker.metrics['idle_unloads']}
            print('PASS',key,'four budgets, separate caches, idle unload/reload, invalid-input rejection',flush=True)
    finally:
        pool.close()
    # Exercise the same download path used by a fresh portable installation.
    manifest=json.loads((ROOT/'runtime/lc0-install.json').read_text())
    entry=manifest['weights']['meangirl7']
    with tempfile.TemporaryDirectory() as folder:
        target=Path(folder)/'meangirl-7.pb.gz'
        download(entry['url'],target,entry['sha256'])
        assert target.stat().st_size>100000
        bad=Path(folder)/'bad.pb.gz'
        try:download(entry['url'],bad,'0'*64)
        except RuntimeError:pass
        else:raise AssertionError('Corrupt checksum was accepted')
        assert not bad.exists() and not bad.with_suffix('.gz.part').exists()
    print('PASS fresh download/checksum verification and partial-file cleanup',flush=True)
    (ROOT/'lc0-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print('ALL LC0 CHECKS PASSED',flush=True)

if __name__=='__main__':main()
