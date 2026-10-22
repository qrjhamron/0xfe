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
                    + " return s ? JSON.stringify(s) : ''; }";
    private static final String CLEAR_ARROW_JS =
            "() => { document.querySelectorAll('#human-engine-arrow')"
                    + ".forEach(e => e.remove()); return true; }";
    private static final int POLL_MS = 300;
    private static final int MOVE_TIME_MS = 700;

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
        handler = new Handler(Looper.getMainLooper());
        if (savedInstanceState == null) {
            webView.loadUrl(START_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
        handler.post(this::pollLoop);
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
        handler.removeCallbacksAndMessages(null);
        executor.shutdownNow();
        engine.close();
        webView.destroy();
        super.onDestroy();
    }

    private void pollLoop() {
        if (destroyed) {
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
            pendingKey = key;
            executor.execute(() -> {
                String move = engine.bestMove(fen, skill, MOVE_TIME_MS);
                runOnUiThread(() -> showMove(key, fen, token, skill, move));
            });
        } catch (Exception e) {
            injectPanel();
        }
    }

    private void showMove(String key, String fen, String token, int skill, String move) {
        if (destroyed || !key.equals(latestKey)) {
            return;
        }
        pendingKey = "";
        if (move == null) {
            return;
        }
        try {
            JSONObject payload = new JSONObject();
            payload.put("fen", fen);
            payload.put("move", move);
            payload.put("skill", skill);
            payload.put("elo", SkillLevel.eloFor(skill));
            payload.put("san", move);
            payload.put("token", token);
            String js = "(" + overlayJs + ")(" + payload + ");";
            webView.evaluateJavascript(js, null);
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
    }

    private String readAsset(String name) {
        try (InputStream input = getAssets().open(name)) {
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }
}
