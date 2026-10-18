# Native Windows UI/UX plan

This is the next shell for Move Coach. The current panel and Chromium adapter
remain the compatibility path while the native app is built; engine and rating
behavior stay shared so a UI migration does not silently change play.

## Product shape

- **Shell:** WinUI 3 (Windows App SDK) with a small tray process. The default
  window is resizable, remembers its monitor and DPI, and never requires a
  browser tab or CDP port.
- **Board:** a native, GPU-accelerated chessboard control with keyboard and
  pointer input, orientation, last-move highlight, legal move hints, and the
  existing recommendation arrows. Board rendering and pointer hit-testing are
  separate from engine state so animation cannot delay a move result.
- **Coach rail:** a fixed-width right rail for level buttons, engine status,
  arrows, adaptive delay, premove queue, and compact
  move/evaluation history. On narrow windows the rail becomes a bottom drawer;
  settings never cover the board permanently.
- **Game strip:** clocks, side to move, runtime indicator, new game, pause, and
  analysis toggle. Maia 3 appears as a human-play mode with a fixed target-level
  selector; weights, node counts, and implementation names stay out of normal
  play.

## State boundaries

1. `GameState` owns FEN, SAN history, orientation, clocks, turn and game
   identity. It is the single source for the board, arrows and premove queue.
2. `CoachService` owns engine workers (Stockfish, Lc0, Maia 3), cache keys,
   incremental analysis and CPU/GPU fallback. It exposes cancellable requests
   and typed results rather than UI-specific JSON.
3. `AutomationService` owns adaptive delay, mouse animation, promotion choice,
   and the maximum three queued premoves. It rejects stale game tokens and
   illegal moves before touching the board.
4. `PreferencesStore` persists appearance, fixed level, delay and
   window placement atomically under the app's per-user data folder.
5. `NativeBridge` starts the existing Python daemon as a local child process
   for the first native milestone. A later bridge can host the same contracts
   in a packaged service without changing the WinUI controls.

## UX rules

- The selected level is a fixed button and always shows its calibrated range;
  there is no free Elo slider.
- Maia, Lc0 and Stockfish show a plain-language runtime chip (`Ready`, `CPU`,
  `GPU`, `Fallback`) with a diagnostics tooltip. A missing optional engine
  disables its card and explains how to install it.
- Adaptive delay visibly locks the numeric delay field, and the disabled state
  is announced to keyboard and screen-reader users.
- Arrows have one clear primary recommendation, optional faint alternatives,
  and a legend that identifies source and freshness. A stale result disappears
  immediately when turn, game or FEN changes.
- Every automation action has a stop shortcut (`Esc`) and a tray pause action.

## Delivery steps

1. **Foundation:** create the WinUI shell, settings store, tray lifecycle and
   typed `GameState`/`CoachService` bridge; add high-DPI and keyboard tests.
2. **Board:** port board rendering and arrows, then compare FEN, orientation,
   and stale-result behavior against current native contract checks.
3. **Coach rail:** port fixed levels, Maia card, runtime chips and
   adaptive delay with persisted preferences.
4. **Automation:** port clocks, premove validation, promotion and stop/pause;
   run deterministic replay tests before enabling online adapters.
5. **Release:** ship the native shell beside the compatibility launcher, gather
   startup and engine-failure diagnostics locally only, then make the native
   shell default after a clean migration run.

## Acceptance gates

The native build is ready for default use when it starts without a browser,
restores a saved game and window layout, shows Maia 3 offline, survives a GPU
engine failure by switching to CPU, preserves the same move and arrow decisions
as the current daemon for a replay fixture, and passes keyboard-only and
100%–200% DPI checks.
