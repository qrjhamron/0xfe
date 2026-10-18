"""Continue sequential validation after the running 480-game job finishes."""
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parent
started=time.monotonic()
while True:
    log=(ROOT/'runtime/calibration-v6.log').read_text()
    if 'V6 CALIBRATION COMPLETE' in log:break
    if time.monotonic()-started>14400:raise TimeoutError('Calibration did not finish within four hours')
    time.sleep(2)
for script in ['analyze_v6.py','validate_v6.py','finalize_v6.py']:
    print('START',script,flush=True)
    subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,check=True)
    print('FINISHED',script,flush=True)
print('V6 ANALYSIS AND VALIDATION COMPLETE',flush=True)
