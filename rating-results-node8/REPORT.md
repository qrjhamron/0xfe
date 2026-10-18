# Four Gyal weights: local 8-node performance test

**This is performance against Stockfish 19 UCI_Elo settings, not verified Chess.com or FIDE Elo.**

Each weight played 48 games: 24 hand-selected opening positions, each with colors swapped. There were 12 games per reference setting (1320, 1600, 1900, 2200). Lc0 v0.32.1 used Eigen CPU, 1 thread, minibatch 1, nodes=8 and a 2 s search ceiling. Stockfish used 1 thread, 16 MiB hash, strength limiting, and 50 ms per move. Up to two games ran concurrently on a 2-core CPU quota. Neither engine used an external opening book or endgame tablebases.

| Weight | W–D–L | Points | Local performance | 95% sampling interval |
|---|---:|---:|---:|---:|
| Bad Gyal 8 | 34–7–7 | 37.5/48 | 2126 | 2007–2246 |
| Mean Girl 7 | 14–13–21 | 20.5/48 | 1661 | 1542–1779 |
| Good Gyal 5 | 22–11–15 | 27.5/48 | 1844 | 1739–1952 |
| Evil Gyal 6 | 18–11–19 | 23.5/48 | 1739 | 1622–1858 |

## Compared with 1 node

| Weight | 1-node estimate | Current estimate | Change | 95% sampling interval for change |
|---|---:|---:|---:|---:|
| Bad Gyal 8 | 1739 | 2126 | +387 | +207 to +566 |
| Mean Girl 7 | 1514 | 1661 | +147 | -14 to +317 |
| Good Gyal 5 | 1555 | 1844 | +289 | +144 to +439 |
| Evil Gyal 6 | 1608 | 1739 | +131 | -78 to +331 |

Intervals for changes jointly resample matched opening/color pairs between runs. The Stockfish opponents choose moves stochastically and were limited by wall time; differences include run variability and are not an exact causal Elo gain.

## How to interpret the numbers

The performance is fitted with the standard logistic Elo expected-score formula `p = 1/(1 + 10**((reference - performance)/400))`, treating draws as half points. The interval uses 5,000 bootstrap resamples of opening/color pairs within each reference level. It reflects sampling variability only. It excludes systematic error from Stockfish calibration, very short thinking time, hardware, openings, and the draw protocol. A UCI_Elo setting is a requested strength, not an independent rating certificate; these results cannot establish a Chess.com/FIDE rating or that the four reference strengths are precisely separated as their labels imply. Overlapping intervals do not establish a reliable ordering. Higher node budgets need a new tournament.

Threefold repetition and 50-move draws were claimed when available. Games were played without evaluation-based win/loss adjudication. A 300-ply cap is an administrative draw and is counted separately below. Forced opening moves are included in PGNs; engines choose moves only after those lines. The fitted estimate applies to this test protocol, not to every position.

## Results by reference

| Weight | Reference | W–D–L | Points |
|---|---:|---:|---:|
| Bad Gyal 8 | 1320 | 12–0–0 | 12/12 |
| Bad Gyal 8 | 1600 | 10–2–0 | 11/12 |
| Bad Gyal 8 | 1900 | 6–2–4 | 7/12 |
| Bad Gyal 8 | 2200 | 6–3–3 | 7.5/12 |
| Mean Girl 7 | 1320 | 9–2–1 | 10/12 |
| Mean Girl 7 | 1600 | 3–3–6 | 4.5/12 |
| Mean Girl 7 | 1900 | 2–3–7 | 3.5/12 |
| Mean Girl 7 | 2200 | 0–5–7 | 2.5/12 |
| Good Gyal 5 | 1320 | 11–1–0 | 11.5/12 |
| Good Gyal 5 | 1600 | 7–3–2 | 8.5/12 |
| Good Gyal 5 | 1900 | 2–5–5 | 4.5/12 |
| Good Gyal 5 | 2200 | 2–2–8 | 3/12 |
| Evil Gyal 6 | 1320 | 11–0–1 | 11/12 |
| Evil Gyal 6 | 1600 | 4–2–6 | 5/12 |
| Evil Gyal 6 | 1900 | 3–3–6 | 4.5/12 |
| Evil Gyal 6 | 2200 | 0–6–6 | 3/12 |

## Terminations

- Bad Gyal 8: checkmate: 41, threefold_repetition: 6, insufficient_material: 1
- Mean Girl 7: threefold_repetition: 12, checkmate: 35, insufficient_material: 1
- Good Gyal 5: threefold_repetition: 11, checkmate: 37
- Evil Gyal 6: checkmate: 37, threefold_repetition: 11

## Reproduce

From the project directory, run `.venv/bin/python rate_weights.py --nodes 8` and then `.venv/bin/python summarize_ratings.py --folder rating-results-node8`. Run `.venv/bin/python verify_rating_results.py --folder rating-results-node8` to audit every saved game. Existing JSONL files are resumed only with matching settings. Stockfish strength limiting has stochastic move selection, so fresh runs will vary. The ZIP contains source, configuration, per-game JSONL and full PGNs.
