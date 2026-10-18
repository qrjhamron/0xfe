"""Server-side fixed levels backed by audited calibration data."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from lc0_config import WEIGHTS
from app_paths import ROOT

@dataclass(frozen=True)
class Preset:
    elo: int
    engine: str
    nodes: int
    measured: bool
    estimate: int
    interval: tuple
    games: int
    enabled: bool = True


def _load():
    data=json.loads((ROOT/'calibration-profiles.json').read_text())
    if data.get('version')==7:
        if data.get('total_games')!=360 or not data.get('created_utc'):
            raise ValueError('Data kalibrasi V7 tidak lengkap. Gunakan paket aplikasi lengkap.')
    elif data.get('version')==6:
        if data.get('total_games')!=744 or not data.get('validated_utc'):
            raise ValueError('Data kalibrasi belum lengkap. Gunakan paket aplikasi lengkap.')
    else:
        raise ValueError('Data kalibrasi belum lengkap. Gunakan paket aplikasi lengkap.')
    if set(data['presets'])!={str(elo) for elo in range(1500,2301,100)}:
        raise ValueError('Daftar level tidak lengkap.')
    result={}
    for label,value in sorted(data['presets'].items(),key=lambda pair:int(pair[0])):
        if value['engine'] not in WEIGHTS or type(value['nodes']) is not int or not 1<=value['nodes']<=256:
            raise ValueError('Konfigurasi level tidak valid.')
        if value['games']!=60 or type(value['estimate']) is not int or len(value['interval'])!=2:
            raise ValueError('Hasil pengujian level tidak lengkap.')
        elo=int(label)
        result[elo]=Preset(elo,value['engine'],value['nodes'],True,value['estimate'],tuple(value['interval']),value['games'],bool(value.get('enabled',True)))
    return result

PRESETS=_load()
CONFIG_ID=hashlib.sha256(json.dumps({'version':7,'prefetch':0,
    'profiles':[(p.elo,p.engine,p.nodes,p.enabled,p.estimate,p.interval,p.games) for p in PRESETS.values()]},sort_keys=True).encode()).hexdigest()[:16]


def resolve_preset(elo,specs):
    if type(elo) is not int or elo not in PRESETS:
        raise ValueError('Pilih salah satu tombol Elo yang tersedia.')
    preset=PRESETS[elo]
    if not preset.enabled or not specs[preset.engine].available:
        raise ValueError('Level ini belum tersedia. Jalankan installer lengkap.')
    return preset


def public_presets(specs):
    return {str(elo):{'available':p.enabled and specs[p.engine].available,'estimate':p.estimate,
                       'interval':list(p.interval),'games':p.games,
                       'target_within_interval':p.interval[0]<=elo<=p.interval[1]} for elo,p in PRESETS.items()}
