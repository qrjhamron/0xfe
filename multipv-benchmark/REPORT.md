# MultiPV A/B benchmark

**Local Stockfish reference performance, not Chess.com/FIDE Elo.**

| Preset | Single-PV | Elo-bounded MultiPV | Change | 95% paired interval |
|---:|---:|---:|---:|---:|
| 1500 | 1477 | 1188 | -289 | -591 to -39 |
| 1600 | 1441 | 1130 | -310 | -593 to -132 |
| 1700 | 1868 | 1188 | -679 | -991 to -450 |
| 1800 | 1767 | 1097 | -670 | -1005 to -424 |
| 1900 | 2071 | 1097 | -974 | -1250 to -755 |
| 2000 | 1885 | 1097 | -788 | -1106 to -569 |
| 2100 | 2297 | 1058 | -1239 | -2261 to -995 |
| 2200 | 2156 | 1214 | -941 | -1212 to -724 |
| 2300 | 2333 | 1097 | -1237 | -1543 to -1026 |

The paired interval resamples identical opening/color pairs. A change whose interval crosses zero is not reliable under this sample. The benchmark controls weight, node budget, openings, colors, reference schedule, and hardware; it still cannot certify an online rating.

| Preset | Mode | Mean own-move ms | Median game seconds |
|---:|---|---:|---:|
| 1500 | single | 3.93 | 2.33 |
| 1500 | multipv | 4.41 | 2.00 |
| 1600 | single | 5.11 | 2.31 |
| 1600 | multipv | 5.65 | 2.40 |
| 1700 | single | 11.01 | 2.98 |
| 1700 | multipv | 12.10 | 2.47 |
| 1800 | single | 10.73 | 2.26 |
| 1800 | multipv | 12.24 | 2.60 |
| 1900 | single | 44.82 | 3.58 |
| 1900 | multipv | 48.90 | 4.95 |
| 2000 | single | 13.61 | 3.05 |
| 2000 | multipv | 15.83 | 3.53 |
| 2100 | single | 53.85 | 4.98 |
| 2100 | multipv | 59.98 | 4.64 |
| 2200 | single | 82.88 | 5.13 |
| 2200 | multipv | 90.89 | 8.38 |
| 2300 | single | 101.54 | 5.89 |
| 2300 | multipv | 98.46 | 7.72 |
- 1500: single 6–11–31; MultiPV 3–3–42
- 1600: single 5–11–32; MultiPV 2–3–43
- 1700: single 17–12–19; MultiPV 3–3–42
- 1800: single 17–6–25; MultiPV 1–4–43
- 1900: single 22–14–12; MultiPV 0–6–42
- 2000: single 16–15–17; MultiPV 1–4–43
- 2100: single 31–9–8; MultiPV 2–1–45
- 2200: single 25–13–10; MultiPV 3–4–41
- 2300: single 32–9–7; MultiPV 1–4–43
