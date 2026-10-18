# Four Gyal weights: local 1-node performance test

**This is performance against Stockfish 19 UCI_Elo settings, not verified Chess.com or FIDE Elo.**

Each weight played 48 games: 24 hand-selected opening positions, each with colors swapped. There were 12 games per reference setting (1320, 1600, 1900, 2200). Lc0 v0.32.1 used Eigen CPU, 1 thread, minibatch 1, nodes=1 and a 2 s search ceiling. Stockfish used 1 thread, 16 MiB hash, strength limiting, and 50 ms per move. Up to two games ran concurrently on a 2-core CPU quota. Neither engine used an external opening book or endgame tablebases.

| Weight | W–D–L | Points | Local performance | 95% sampling interval |
|---|---:|---:|---:|---:|
| Bad Gyal 8 | 19–9–20 | 23.5/48 | 1739 | 1608–1871 |
| Mean Girl 7 | 10–10–28 | 15/48 | 1514 | 1400–1608 |
| Good Gyal 5 | 10–13–25 | 16.5/48 | 1555 | 1444–1661 |
| Evil Gyal 6 | 11–15–22 | 18.5/48 | 1608 | 1473–1739 |

## How to interpret the numbers

The performance is fitted with the standard logistic Elo expected-score formula `p = 1/(1 + 10**((reference - performance)/400))`, treating draws as half points. The interval uses 5,000 bootstrap resamples of opening/color pairs within each reference level. It reflects sampling variability only. It excludes systematic error from Stockfish calibration, very short thinking time, hardware, openings, and the draw protocol. A UCI_Elo setting is a requested strength, not an independent rating certificate; these results cannot establish a Chess.com/FIDE rating or that the four reference strengths are precisely separated as their labels imply. Overlapping intervals do not establish a reliable ordering. Higher node budgets need a new tournament.

Threefold repetition and 50-move draws were claimed when available. Games were played without evaluation-based win/loss adjudication. A 300-ply cap is an administrative draw and is counted separately below. Forced opening moves are included in PGNs; engines choose moves only after those lines. The fitted estimate applies to this test protocol, not to every position.

## Results by reference

| Weight | Reference | W–D–L | Points |
|---|---:|---:|---:|
| Bad Gyal 8 | 1320 | 11–0–1 | 11/12 |
| Bad Gyal 8 | 1600 | 3–2–7 | 4/12 |
| Bad Gyal 8 | 1900 | 4–4–4 | 6/12 |
| Bad Gyal 8 | 2200 | 1–3–8 | 2.5/12 |
| Mean Girl 7 | 1320 | 8–3–1 | 9.5/12 |
| Mean Girl 7 | 1600 | 2–5–5 | 4.5/12 |
| Mean Girl 7 | 1900 | 0–1–11 | 0.5/12 |
| Mean Girl 7 | 2200 | 0–1–11 | 0.5/12 |
| Good Gyal 5 | 1320 | 6–3–3 | 7.5/12 |
| Good Gyal 5 | 1600 | 2–3–7 | 3.5/12 |
| Good Gyal 5 | 1900 | 0–2–10 | 1/12 |
| Good Gyal 5 | 2200 | 2–5–5 | 4.5/12 |
| Evil Gyal 6 | 1320 | 5–5–2 | 7.5/12 |
| Evil Gyal 6 | 1600 | 3–6–3 | 6/12 |
| Evil Gyal 6 | 1900 | 2–1–9 | 2.5/12 |
| Evil Gyal 6 | 2200 | 1–3–8 | 2.5/12 |

## Terminations

- Bad Gyal 8: checkmate: 39, threefold_repetition: 8, insufficient_material: 1
- Mean Girl 7: checkmate: 38, threefold_repetition: 8, insufficient_material: 1, stalemate: 1
- Good Gyal 5: threefold_repetition: 12, checkmate: 35, stalemate: 1
- Evil Gyal 6: threefold_repetition: 14, checkmate: 33, insufficient_material: 1

## Reproduce

From the project directory, run `.venv/bin/python rate_weights.py` and then `.venv/bin/python summarize_ratings.py`. Run `.venv/bin/python verify_rating_results.py` to audit every saved game. Existing JSONL files are resumed only with matching settings. Stockfish strength limiting has stochastic move selection, so fresh runs will vary. The ZIP contains source, configuration, per-game JSONL and full PGNs.
