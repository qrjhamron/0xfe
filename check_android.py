"""Static checks for the Android Patricia build (no JDK or SDK needed).

Guards the Android contract: Patricia is the only engine, Skill_Level 1-18
only, and no code path in the app moves or queues pieces on the board.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANDROID = ROOT / 'android'
MAIN = ANDROID / 'app/src/main'

EXPECTED_ELO = [500, 800, 1000, 1200, 1300, 1400, 1500, 1600, 1700,
                1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2650]

required = [
    ANDROID / 'settings.gradle', ANDROID / 'build.gradle',
    ANDROID / 'app/build.gradle', MAIN / 'AndroidManifest.xml',
    MAIN / 'java/com/movecoach/android/MainActivity.java',
    MAIN / 'java/com/movecoach/android/PatriciaEngine.java',
    MAIN / 'java/com/movecoach/android/SkillLevel.java',
    MAIN / 'assets/panel.js', MAIN / 'assets/overlay.js',
    ANDROID / 'build-patricia.sh', ANDROID / 'README.md',
    ROOT / '.github/workflows/android.yml',
]
missing = [str(path) for path in required if not path.is_file()]
assert not missing, f'missing Android files: {missing}'
print('PASS: Android project files are present')

skill_java = (MAIN / 'java/com/movecoach/android/SkillLevel.java').read_text()
elo_block = re.search(r'ELO\s*=\s*\{([^}]+)\}', skill_java).group(1)
elo_table = [int(value) for value in re.findall(r'\d+', elo_block)]
assert elo_table == EXPECTED_ELO, elo_table
assert 'MAX = 18' in skill_java and 'MIN = 1' in skill_java
assert elo_table == sorted(elo_table) and len(set(elo_table)) == 18
print('PASS: SkillLevel offers exactly 1-18 with Patricia Elo labels')

app_sources = ''
for path in [MAIN / 'assets/panel.js', MAIN / 'assets/overlay.js',
             MAIN / 'java/com/movecoach/android/MainActivity.java',
             MAIN / 'java/com/movecoach/android/PatriciaEngine.java']:
    app_sources += path.read_text().lower() + '\n'
for token in ('premove', 'automove', 'queuenative', 'automationresult',
              'dispatchgesture', 'page.mouse', 'motionevent'):
    assert token not in app_sources, f'forbidden board-input token in Android app: {token}'
print('PASS: no auto-move or premove code path exists in the Android app')

engine_java = (MAIN / 'java/com/movecoach/android/PatriciaEngine.java').read_text()
assert 'setoption name Skill_Level value ' in engine_java
assert '"go movetime " +' in engine_java or '"go movetime "' in engine_java
assert 'libpatricia.so' in (MAIN / 'java/com/movecoach/android/MainActivity.java').read_text()
manifest = (MAIN / 'AndroidManifest.xml').read_text()
assert 'android:extractNativeLibs="true"' in manifest
panel_js = (MAIN / 'assets/panel.js').read_text()
assert 'skillLevels' in panel_js and 'prefs.skill' in (MAIN / 'assets/overlay.js').read_text()
print('PASS: Patricia UCI bridge, Skill_Level option, and extracted engine binary are wired')

# Regression guard for the blinking-buttons bug: a connected panel must
# never be moved between containers, and a dropped panel must be restored
# by observer in the same frame, not by the next native poll.
assert "if (panel.isConnected && !panel.classList.contains('coach-floating')) return;" in panel_js
assert 'panel.parentNode !== sidebar' not in panel_js
assert 'MutationObserver' in panel_js and 'mountObserver.disconnect()' in panel_js
print('PASS: panel mounting is stable and self-healing (no blink oscillation)')

# Regression guard for the missing-panel bug: the panel must be created
# before any board exists and float above the page until it can anchor.
assert "if (!document.querySelector(boardSelector)?.game) return null" not in panel_js
assert 'coach-floating' in panel_js and 'document.body?.appendChild(panel)' in panel_js
assert '__panel__' in (MAIN / 'java/com/movecoach/android/MainActivity.java').read_text()
print('PASS: panel is created without a board and floats until anchored')

# SAN labels, position score, and render/poll efficiency wiring.
java_dir = MAIN / 'java/com/movecoach/android'
assert (java_dir / 'San.java').is_file() and (java_dir / 'ScoreFormat.java').is_file()
main_java = (java_dir / 'MainActivity.java').read_text()
assert 'San.toSan' in main_java and 'ScoreFormat.format' in main_java
assert 'onPause' in main_java and 'stopPolling' in main_java
assert 'San.toSan' not in panel_js and 'renderedSignature' in panel_js
assert 'score' in (MAIN / 'assets/overlay.js').read_text()
print('PASS: SAN labels, White-POV score, and render-on-change are wired')

build_script = (ANDROID / 'build-patricia.sh').read_text()
assert '67d83d7056801cfab868872d27b99d192488a316' in build_script
assert 'aarch64-linux-android26' in build_script and 'libpatricia.so' in build_script
assert '-static-libstdc++' in build_script
workflow = (ROOT / '.github/workflows/android.yml').read_text()
assert 'build-patricia.sh' in workflow and 'assembleDebug' in workflow
assert 'setup-ndk' in workflow and 'ANDROID_NDK_HOME' in workflow
assert 'testDebugUnitTest' in workflow and 'upload-artifact' in workflow
print('PASS: GitHub Actions builds pinned Patricia with the Android NDK')

# Regression guard for the eternal "preparing" bug: engine waits must have
# real deadlines, failures must restart the process, and the panel must be
# able to say why instead of spinning forever.
assert 'ArrayBlockingQueue' in engine_java and 'lastError' in engine_java
assert 'Patricia tidak merespons' in engine_java
assert 'engineStatus' in panel_js and 'engineStatusText' in panel_js
assert 'panelEngineStatus' in main_java and 'retryAtMs' in main_java
print('PASS: engine timeouts, restart, and visible failure status are wired')

# Regression guard for moves arriving already stale: the request token may
# only contain stable facts, the overlay must name its rejection, a rejected
# arrow must still surface as panel text, and the engine must self-test.
assert '[fen, side, prefs.skill, revision]' in panel_js
assert 'gameId, fen, phase, side, reason' not in panel_js
overlay_js = (MAIN / 'assets/overlay.js').read_text()
assert 'getOptions?.()' in overlay_js and "'stale-token'" in overlay_js
assert 'STARTING_FEN' in main_java and 'Mesin siap' in main_java
assert 'report(p)' in main_java and 'Langkah tidak tampil' in main_java
print('PASS: stable tokens, named rejections, text fallback, and engine self-test')

print('ALL ANDROID CHECKS PASSED')
