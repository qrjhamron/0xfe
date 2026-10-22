package com.movecoach.android;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * Minimal UCI client for the bundled Patricia executable.
 *
 * One engine process is kept alive and reused. Calls are serialized by the
 * caller; a failed process is dropped and restarted on the next request.
 */
public final class PatriciaEngine {
    private final File binary;
    private Process process;
    private BufferedReader reader;
    private BufferedWriter writer;
    private int currentSkill = -1;

    public PatriciaEngine(File binary) {
        this.binary = binary;
    }

    /** Returns the best move in UCI notation, or null when unavailable. */
    public synchronized String bestMove(String fen, int skill, int moveTimeMs) {
        try {
            ensureStarted();
            int clamped = SkillLevel.clamp(skill);
            if (clamped != currentSkill) {
                send("setoption name Skill_Level value " + clamped);
                currentSkill = clamped;
            }
            send("position fen " + fen);
            send("go movetime " + moveTimeMs);
            long deadline = System.nanoTime()
                    + TimeUnit.MILLISECONDS.toNanos(moveTimeMs + 10000L);
            String line;
            while (System.nanoTime() < deadline && (line = reader.readLine()) != null) {
                if (line.startsWith("bestmove")) {
                    String[] parts = line.split("\\s+");
                    return parts.length > 1 ? parts[1] : null;
                }
            }
        } catch (IOException | RuntimeException e) {
            close();
        }
        return null;
    }

    public synchronized void close() {
        if (process != null) {
            try {
                send("quit");
            } catch (IOException | RuntimeException ignored) {
                // The process is going away either way.
            }
            process.destroy();
        }
        process = null;
        reader = null;
        writer = null;
        currentSkill = -1;
    }

    private void ensureStarted() throws IOException {
        if (process != null && process.isAlive()) {
            return;
        }
        close();
        if (!binary.isFile()) {
            throw new IOException("Patricia binary missing: " + binary);
        }
        process = new ProcessBuilder(binary.getAbsolutePath())
                .redirectErrorStream(true)
                .start();
        reader = new BufferedReader(new InputStreamReader(
                process.getInputStream(), StandardCharsets.UTF_8));
        writer = new BufferedWriter(new OutputStreamWriter(
                process.getOutputStream(), StandardCharsets.UTF_8));
        currentSkill = -1;
        send("uci");
        waitFor("uciok", 10000);
        send("isready");
        waitFor("readyok", 10000);
        send("setoption name Threads value 2");
        send("setoption name Hash value 64");
    }

    private void waitFor(String token, long timeoutMs) throws IOException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        String line;
        while (System.nanoTime() < deadline && (line = reader.readLine()) != null) {
            if (line.contains(token)) {
                return;
            }
        }
        throw new IOException("Patricia did not answer " + token);
    }

    private void send(String command) throws IOException {
        writer.write(command);
        writer.newLine();
        writer.flush();
    }
}
