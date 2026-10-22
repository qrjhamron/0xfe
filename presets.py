"""Panel levels backed by Patricia's published Skill_Level table.

Patricia is the only engine: every button maps to the nearest Skill_Level
and its Elo label is Patricia's own estimate for that level, not a locally
calibrated or verified human rating.
"""
from dataclasses import dataclass
import hashlib
import json

from engine_runtime import PATRICIA_SKILL_ELO, patricia_skill_for_elo


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


def _build():
    result = {}
    for elo in range(1000, 2301, 100):
        estimate = PATRICIA_SKILL_ELO[patricia_skill_for_elo(elo) - 1]
        result[elo] = Preset(elo, 'patricia', 16, False, estimate,
                             (estimate, estimate), 0, True)
    return result


PRESETS = _build()
CONFIG_ID = hashlib.sha256(json.dumps(
    {'version': 16,
     'levels': [(p.elo, p.estimate) for p in PRESETS.values()]},
    sort_keys=True).encode()).hexdigest()[:16]


def resolve_preset(elo, specs):
    if type(elo) is not int or elo not in PRESETS:
        raise ValueError('Pilih salah satu tombol Elo yang tersedia.')
    if not specs['patricia'].available:
        raise ValueError('Patricia belum terpasang. Jalankan installer lengkap.')
    return PRESETS[elo]


def public_presets(specs):
    return {str(elo): {'available': specs['patricia'].available,
                       'estimate': p.estimate,
                       'interval': list(p.interval),
                       'games': p.games,
                       'target_within_interval': p.interval[0] <= elo <= p.interval[1]}
            for elo, p in PRESETS.items()}
