package com.movecoach.android;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Chess.com WebView with an injected coach panel.
 *
 * The panel only displays a recommendation arrow for the side to move.
 * Nothing in this app clicks, drags, or queues moves on the board.
 */
public final class MainActivity extends Activity {
    private static final String START_URL = "https://www.chess.com/play/computer";
    private static final String POLL_JS =
            "() => { const a = window.__chessArrowCoach;"
                    + " const s = a ? a.poll() : null;"
                    + " return s ? JSON.stringify(s) : (a ? '__panel__' : ''); }";
    private static final String CLEAR_ARROW_JS =
            "() => { document.querySelectorAll('#human-engine-arrow')"
                    + ".forEach(e => e.remove()); return true; }";
    private static final int POLL_MS = 300;
    private static final int MOVE_TIME_MS = 600;
    private static final String STARTING_FEN =
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

    private WebView webView;
    private Handler handler;
    private ExecutorService executor;
    private PatriciaEngine engine;
    private String panelJs;
    private String overlayJs;
    private String latestKey = "";
    private String pendingKey = "";
    private boolean destroyed;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        setContentView(webView);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                injectPanel();
            }
        });
        panelJs = readAsset("panel.js");
        overlayJs = readAsset("overlay.js");
        engine = new PatriciaEngine(new File(
                getApplicationInfo().nativeLibraryDir, "libpatricia.so"));
        executor = Executors.newSingleThreadExecutor();
        // Prove the engine works inside this app before any game starts;
        // the panel reports the outcome so a dead engine is never silent.
        executor.execute(() -> {
            long started = android.os.SystemClock.uptimeMillis();
            PatriciaEngine.Result probe = engine.bestMove(
                    STARTING_FEN, SkillLevel.DEFAULT, 500);
            long elapsed = android.os.SystemClock.uptimeMillis() - started;
            String notice = probe != null && probe.move != null
                    ? "Mesin siap · tes " + probe.move + " · " + elapsed + " ms"
                    : "Tes mesin gagal · " + engine.lastError();
            runOnUiThread(() -> panelEngineStatus(notice));
        });
        handler = new Handler(Looper.getMainLooper());
        if (savedInstanceState == null) {
            webView.loadUrl(START_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
        startPolling();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        destroyed = true;
        stopPolling();
        executor.shutdownNow();
        engine.close();
        webView.destroy();
        super.onDestroy();
    }

    private boolean polling;

    private void startPolling() {
        if (polling || destroyed) {
            return;
        }
        polling = true;
        handler.post(this::pollLoop);
    }

    private void stopPolling() {
        polling = false;
        handler.removeCallbacksAndMessages(null);
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
        startPolling();
    }

    @Override
    protected void onPause() {
        stopPolling();
        webView.onPause();
        super.onPause();
    }

    private void pollLoop() {
        if (destroyed || !polling) {
            return;
        }
        webView.evaluateJavascript(POLL_JS, value -> handlePoll(value));
        handler.postDelayed(this::pollLoop, POLL_MS);
    }

    private void handlePoll(String value) {
        if (destroyed || value == null) {
            return;
        }
        try {
            Object decoded = new JSONTokener(value).nextValue();
            if (!(decoded instanceof String) || ((String) decoded).isEmpty()) {
                injectPanel();
                return;
            }
            if (decoded.equals("__panel__")) {
                return; // Panel is alive; the board is not ready yet.
            }
            JSONObject snapshot = new JSONObject((String) decoded);
            if (!snapshot.optBoolean("eligible")) {
                latestKey = "";
                webView.evaluateJavascript(CLEAR_ARROW_JS, null);
                return;
            }
            String fen = snapshot.getString("fen");
            String token = snapshot.getString("token");
            int skill = snapshot.optJSONObject("prefs") != null
                    ? snapshot.getJSONObject("prefs").optInt("skill", SkillLevel.DEFAULT)
                    : SkillLevel.DEFAULT;
            String key = token + "|" + skill;
            latestKey = key;
            if (key.equals(pendingKey)) {
                return;
            }
            if (android.os.SystemClock.uptimeMillis() < retryAtMs) {
                return; // Engine recently failed; panel shows why.
            }
            pendingKey = key;
            executor.execute(() -> {
                PatriciaEngine.Result result = engine.bestMove(fen, skill, MOVE_TIME_MS);
                runOnUiThread(() -> showMove(key, fen, token, skill, result));
            });
        } catch (Exception e) {
            injectPanel();
        }
    }

    private long retryAtMs;
    private int consecutiveFailures;
    private volatile String engineNotice = "";

    private void panelEngineStatus(String message) {
        engineNotice = message == null ? "" : message;
        String js = "window.__chessArrowCoach?.engineStatus?.("
                + JSONObject.quote(engineNotice) + ");";
        webView.evaluateJavascript(js, null);
    }

    private void showMove(String key, String fen, String token, int skill,
                          PatriciaEngine.Result result) {
        if (destroyed || !key.equals(latestKey)) {
            if (!destroyed) {
                panelEngineStatus("Jawaban mesin dibuang · posisi sudah berubah");
            }
            return;
        }
        pendingKey = "";
        if (result == null || result.move == null || result.move.length() < 4
                || result.move.equals("(none)")) {
            consecutiveFailures++;
            retryAtMs = android.os.SystemClock.uptimeMillis()
                    + Math.min(5000L, 1000L * consecutiveFailures);
            String error = engine.lastError();
            panelEngineStatus("Mesin tidak merespons · mencoba lagi…"
                    + (error != null ? " (" + error + ")" : ""));
            return;
        }
        consecutiveFailures = 0;
        retryAtMs = 0;
        // SAN is only a label: a conversion problem must never eat the move.
        String san = result.move;
        try {
            String converted = San.toSan(fen, result.move);
            if (converted != null) {
                san = converted;
            }
        } catch (RuntimeException ignored) {
            // Keep the UCI label and still show the arrow.
        }
        try {
            boolean whiteToMove = fen.split(" ")[1].equals("w");
            JSONObject payload = new JSONObject();
            payload.put("fen", fen);
            payload.put("move", result.move);
            payload.put("skill", skill);
            payload.put("elo", SkillLevel.eloFor(skill));
            payload.put("san", san != null ? san : result.move);
            payload.put("score", ScoreFormat.format(
                    result.scoreCp, result.mate, whiteToMove));
            payload.put("token", token);
            String payloadJson = payload.toString();
            String js = "(" + overlayJs + ")(" + payloadJson + ");";
            webView.evaluateJavascript(js, value -> {
                if ("true".equals(value)) {
                    engineNotice = "";
                    return;
                }
                // The arrow was rejected; still show the move as panel text.
                String reportJs = "(p => window.__chessArrowCoach?.report(p))("
                        + payloadJson + ");";
                webView.evaluateJavascript(reportJs, shown -> {
                    if (!"true".equals(shown)) {
                        panelEngineStatus("Langkah tidak tampil · papan "
                                + value + " · panel " + shown);
                    }
                });
            });
        } catch (Exception ignored) {
            // The board moved on; the next poll will request a fresh move.
        }
    }

    private void injectPanel() {
        if (panelJs == null || overlayJs == null) {
            return;
        }
        StringBuilder levels = new StringBuilder("[");
        for (int skill = SkillLevel.MIN; skill <= SkillLevel.MAX; skill++) {
            if (skill > SkillLevel.MIN) {
                levels.append(',');
            }
            levels.append("{\"skill\":").append(skill)
                    .append(",\"elo\":").append(SkillLevel.eloFor(skill)).append('}');
        }
        levels.append(']');
        String options = "{\"skillLevels\":" + levels
                + ",\"defaultSkill\":" + SkillLevel.DEFAULT + "}";
        webView.evaluateJavascript("(" + panelJs + ")(" + options + ");", null);
        if (!engineNotice.isEmpty()) {
            panelEngineStatus(engineNotice);
        }
    }

    private String readAsset(String name) {
        try (InputStream input = getAssets().open(name)) {
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }
}
